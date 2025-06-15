from math import inf, ceil
from datetime import datetime, timedelta
import json

def dateToMinutes(baseline, date):
	fmt = "%Y-%m-%d %H:%M"

	d1 = datetime.strptime(baseline, fmt)
	d2 = datetime.strptime(date, fmt)
	diff_minutes = int((d2 - d1).total_seconds() / 60)
	if diff_minutes < 0:
		diff_minutes = 0

	return diff_minutes

def importData(data):
	requests, jobs, parts, services, machines = {}, {}, {}, {}, {}
	nRequests, nJobs, nParts, nServices, nMachines = 0, 0, 0, 0, 0

	for m in data['machines'].keys():
		machines[nMachines] = {'id': m,
							   'company': data['machines'][m]['company'],
							   'services': [],
							   'processingTimes': data['machines'][m]['processingTimes'][:],
							   'timeWindows': []}
		for s in data['machines'][m]['services']:
			if all(services[t]['name'] != s for t in services.keys()):
				services[nServices] = {'name': s,
									   'machines': [nMachines]}
				machines[nMachines]['services'].append(nServices)
				nServices += 1
			else:
				for t in services.keys():
					if services[t]['name'] == s:
						machines[nMachines]['services'].append(t)
						services[t]['machines'].append(nMachines)
						break
		timeWindows = []
		for t in data['machines'][m]['timeWindows']:
			tw = [s for s in t]
			tw[0] = dateToMinutes(data['date'], tw[0])
			if tw[1] != inf:
				tw[1] = dateToMinutes(data['date'], tw[1])
			else:
				tw[1] = 100_000
			timeWindows.append(tuple(tw))
		machines[nMachines]['timeWindows'] = timeWindows[:]
		nMachines += 1

	transportationTimes = {i: {j: None for j in machines.keys()} for i in machines.keys()}
	for i in machines.keys():
		for j in machines.keys():
			try:
				transportationTimes[i][j] = data['machines'][machines[i]['id']]['transportationTimes'][machines[j]['id']]*60
			except Exception:
				transportationTimes[i][j] = 0

	for r in data['requests'].keys():
		requests[nRequests] = {'id': r,
							   'dueDate': dateToMinutes(data['date'], data['requests'][r]['dueDate'] + " 00:00"),
							   'parts': [],
							   'jobs': [],
							   'services': []}
		for s in data['requests'][r]['services']:
			for t in services.keys():
				if services[t]['name'] == s:
					requests[nRequests]['services'].append(t)
		for p in range(data['requests'][r]['parts']):
			parts[nParts] = {'request': nRequests,
							 'jobs': [],
							 'services': requests[nRequests]['services'][:]}
			for s in parts[nParts]['services']:
				jobs[nJobs] = {'request': nRequests,
							   'part': nParts,
							   'service': s,
							   'previousJob': None,
							   'processingTime': data['requests'][r]['processingParameters'][parts[nParts]['services'].index(s)]}
				parts[nParts]['jobs'].append(nJobs)
				requests[nRequests]['jobs'].append(nJobs)
				if nJobs > 0:
					if jobs[nJobs-1]['part'] == jobs[nJobs]['part'] and jobs[nJobs-1]['request'] == jobs[nJobs]['request']:
						jobs[nJobs]['previousJob'] = nJobs-1
				nJobs += 1
			requests[nRequests]['parts'].append(nParts)
			nParts += 1
		nRequests += 1

	transferTimes = {j: {m: 60*data['requests'][requests[jobs[j]['request']]['id']]['transportationTimes'][machines[m]['id']] for m in machines.keys()} for j in jobs.keys()}
	objectives = data['objectives']
	for r in requests.keys():
		requests[r]['id'] = f"request_{requests[r]['id']}"

	eligibilities = {j: {m: int(bool(jobs[j]['service'] in machines[m]['services'])) for m in machines.keys()} for j in jobs.keys()}
	processingTimes = {j: {m: int(jobs[j]['processingTime']*machines[m]['processingTimes'][machines[m]['services'].index(jobs[j]['service'])]) for m in machines.keys() if eligibilities[j][m] == 1} for j in jobs.keys()}

	return requests, parts, jobs, machines, services, transportationTimes, transferTimes, processingTimes, eligibilities, objectives