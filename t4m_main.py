import json

import t4m_input
import t4m_cp

file = open(f'./input.json', encoding='utf-8')
input_data = json.load(file)
requests, parts, jobs, machines, services, transportationTimes, transferTimes, processingTimes, eligibilities, objectives = t4m_input.importData(input_data)


solutions = t4m_cp.cp(input_data['date'], jobs, parts, requests, machines, services, transportationTimes, transferTimes, processingTimes, eligibilities, objectives)

with open(f"./output.json", 'w') as outfile:
	json.dump(solutions, outfile, indent = 4)
