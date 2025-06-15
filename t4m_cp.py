import cplex
from cplex.exceptions import CplexSolverError
from docplex.cp.model import CpoModel
import warnings
warnings.filterwarnings("ignore")
from math import inf
from datetime import datetime, timedelta
import random, copy

def minutesToDate(baseline, minutes): # Converts minutes to datetimes
	fmt = "%Y-%m-%d %H:%M"

	d1 = datetime.strptime(baseline, fmt)
	d2 = d1 + timedelta(minutes=minutes)
	dt2 = d2.strftime(fmt)

	return dt2

def cp(basedate, jobs, parts, requests, machines, services, transportationTimes, transferTimes, processingTimes, alpha, objectives):
	timelimit, printLog, solutions, nSolutions, timeWindows, nTW = 30, False, {}, 1, {}, 0
	for m in machines.keys():
		for t in machines[m]['timeWindows']:
			t = list(t)
			timeWindows[nTW] = {'machine': m, 'tw': t}
			nTW += 1
	maxSolutions, coefficients = 5, []
	if len(objectives) > 1:
		for s in range(maxSolutions):
			newCoefficients = []
			for o in range(len(objectives)):
				if o < len(objectives)-1:
					random.seed(((s+o)*(s+o+1)/2) + 2)
					value = round(random.uniform(0.0, 1.0 - sum(newCoefficients)), 2)
					newCoefficients.append(value)
				else:
					newCoefficients.append(round(1.0 - sum(newCoefficients), 2))
			coefficients.append(newCoefficients)
	else:
		coefficients.append([1.0])

	for co in coefficients:
		model = CpoModel()

		makespan = model.integer_var(0, 100_000, name = 'makespan')
		locality = model.integer_var(0, 100_000, name = 'locality')
		
		jobIntervalA = {(j, m, t): model.interval_var(start = (timeWindows[t]['tw'][0], min([timeWindows[t]['tw'][1], requests[jobs[j]['request']]['dueDate']])),
													  end = (timeWindows[t]['tw'][0], min([timeWindows[t]['tw'][1], requests[jobs[j]['request']]['dueDate']])),
													  size = (processingTimes[j][m], processingTimes[j][m]),
													  optional = True,
													  name = f'jobA_{j},{m},{t}') for j in jobs.keys() for m in machines.keys() if alpha[j][m] == 1 for t in timeWindows.keys() if timeWindows[t]['machine'] == m and timeWindows[t]['tw'][0] <= requests[jobs[j]['request']]['dueDate']}
		jobIntervalB = {(j, m): model.interval_var(size = (processingTimes[j][m], processingTimes[j][m]),
												   optional = True,
												   name = f'jobB_{j},{m}') for j in jobs.keys() for m in machines.keys() if alpha[j][m] == 1}
		machineSequence = {m: model.sequence_var([jobIntervalB[(j, m)] for j in jobs.keys() if alpha[j][m] == 1], name = f'machine_{m}') for m in machines.keys()}

		
		for j in jobs.keys():
			for i in jobs.keys():
				if jobs[j]['request'] == jobs[i]['request'] and jobs[j]['part'] > jobs[i]['part'] and jobs[j]['service'] == jobs[i]['service']:
					for m in machines.keys():
						if alpha[j][m] == 1:
							for n in machines.keys():
								if alpha[i][n] == 1:
									model.add(model.if_then((model.presence_of(jobIntervalB[(j, m)])*model.presence_of(jobIntervalB[(i, n)]) == 1), (model.end_of(jobIntervalB[(j, m)]) >= model.end_of(jobIntervalB[(i, n)]))))

		for j in jobs.keys():
			model.add(sum(model.presence_of(jobIntervalB[(j, m)]) for m in machines.keys() if alpha[j][m] == 1) == 1)
			for m in machines.keys():
				if alpha[j][m] == 1:
					model.add(model.alternative(jobIntervalB[(j, m)], [jobIntervalA[(j, m, t)] for t in timeWindows.keys() if timeWindows[t]['machine'] == m]))

		for m in machines.keys():
			model.add(model.no_overlap(machineSequence[m]))
			for j in jobs.keys():
				if alpha[j][m] == 1 and jobs[j]['previousJob'] != None:
					for n in machines.keys():
						if alpha[jobs[j]['previousJob']][n] == 1:
							model.add(model.end_before_start(jobIntervalB[(jobs[j]['previousJob'], n)], jobIntervalB[(j, m)], transportationTimes[n][m]))
				if alpha[j][m] == 1 and jobs[j]['previousJob'] == None:
					model.add(model.start_of(jobIntervalB[(j, m)]) >= transferTimes[j][m]*model.presence_of(jobIntervalB[(j, m)]))
				if alpha[j][m] == 1:
					model.add(makespan >= model.end_of(jobIntervalB[(j, m)]))
		model.add(locality >= sum(transferTimes[j][m]*model.presence_of(jobIntervalB[(j, m)]) for j in jobs.keys() for m in machines.keys() if alpha[j][m] == 1))

		objectiveFunction = 0
		for o in objectives:
			if o == 'makespan':
				objectiveFunction += co[objectives.index(o)]*makespan
			if o == 'locality':
				objectiveFunction += co[objectives.index(o)]*locality
		model.add(model.minimize(objectiveFunction))
		if len(objectives) > 1:
			sol = model.solve(TimeLimit = timelimit, trace_log = printLog)
			if sol:
				newSolution = {"objectives": {}, "schedule": {}}
				for o in objectives:
					if o == 'makespan':
						newSolution['objectives'][o] = sol[makespan]
					if o == 'locality':
						newSolution['objectives'][o] = sol[locality]
				for r in requests.keys():
					newSolution['schedule'][requests[r]['id']] = {}
					nParts = 1
					for p in requests[r]['parts']:
						newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)] = {}
						for s in parts[p]['services']:
							newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']] = {}
							for j in jobs.keys():
								if jobs[j]['request'] == r and jobs[j]['part'] == p and jobs[j]['service'] == s:
									for m in machines.keys():
										if alpha[j][m] == 1:
											if len(sol[jobIntervalB[(j, m)]]) > 0:
												newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['machine'] = machines[m]['id']
												newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['start'] = minutesToDate(basedate, sol[jobIntervalB[(j, m)]][0])
												newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['end'] = minutesToDate(basedate, sol[jobIntervalB[(j, m)]][1])
												newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['provider'] = machines[m]['company']
						nParts += 1
				solutions[f"composition_{nSolutions}"] = copy.deepcopy(newSolution)
				nSolutions += 1
				for i in parts.keys():
					constraint = 0
					for j in parts[i]['jobs']:
						for m in machines.keys():
							if alpha[j][m] == 1:
								if len(sol[jobIntervalB[(j, m)]]) > 0:
									provider = machines[m]['company']
									break
						constraint += sum(model.presence_of(jobIntervalB[(j, m)]) for m in machines.keys() if machines[m]['company'] == provider and alpha[j][m] == 1)
					model.add(constraint <= len([j for j in parts[i]['jobs']])-1)
				#model.add(sum(model.presence_of(jobIntervalB[(j, m)]) for j in jobs.keys() if sum([alpha[j][m] for m in machines.keys()]) > 1 for m in machines.keys() if alpha[j][m] == 1 and len(sol[jobIntervalB[(j, m)]]) > 0) <= len([j for j in jobs.keys() if sum([alpha[j][m] for m in machines.keys()]) > 1])/len(requests.keys()))
			else:
				break
		else:
			while(nSolutions <= maxSolutions):
				sol = model.solve(TimeLimit = timelimit, trace_log = printLog)
				if sol:
					newSolution = {"objectives": {}, "schedule": {}}
					for o in objectives:
						if o == 'makespan':
							newSolution['objectives'][o] = sol[makespan]
						if o == 'locality':
							newSolution['objectives'][o] = sol[locality]
					for r in requests.keys():
						newSolution['schedule'][requests[r]['id']] = {}
						nParts = 1
						for p in requests[r]['parts']:
							newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)] = {}
							for s in parts[p]['services']:
								newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']] = {}
								for j in jobs.keys():
									if jobs[j]['request'] == r and jobs[j]['part'] == p and jobs[j]['service'] == s:
										for m in machines.keys():
											if alpha[j][m] == 1:
												if len(sol[jobIntervalB[(j, m)]]) > 0:
													newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['machine'] = machines[m]['id']
													newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['start'] = minutesToDate(basedate, sol[jobIntervalB[(j, m)]][0])
													newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['end'] = minutesToDate(basedate, sol[jobIntervalB[(j, m)]][1])
													newSolution['schedule'][requests[r]['id']]["part_"+str(nParts)][services[s]['name']]['provider'] = machines[m]['company']
							nParts += 1
					solutions[f"composition_{nSolutions}"] = copy.deepcopy(newSolution)
					nSolutions += 1
					for i in parts.keys():
						constraint = 0
						for j in parts[i]['jobs']:
							for m in machines.keys():
								if alpha[j][m] == 1:
									if len(sol[jobIntervalB[(j, m)]]) > 0:
										provider = machines[m]['company']
										break
							constraint += sum(model.presence_of(jobIntervalB[(j, m)]) for m in machines.keys() if machines[m]['company'] == provider and alpha[j][m] == 1)
						model.add(constraint <= len([j for j in parts[i]['jobs']])-1)
					#model.add(sum(model.presence_of(jobIntervalB[(j, m)]) for j in jobs.keys() if sum([alpha[j][m] for m in machines.keys()]) > 1 for m in machines.keys() if alpha[j][m] == 1 and len(sol[jobIntervalB[(j, m)]]) > 0) <= len([j for j in jobs.keys() if sum([alpha[j][m] for m in machines.keys()]) > 1])/len(requests.keys()))
				else:
					break
	return solutions
