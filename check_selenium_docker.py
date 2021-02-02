#!/usr/bin/env python3
"""
    Copyright (C) 2020  Opsdis Consulting AB <https://opsdis.com/>
    This file is part of check_selenium_docker.
    check_selenium_docker is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    check_selenium_docker is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with check_selenium_docker.  If not, see <http://www.gnu.org/licenses/>.
"""

import docker
import os, sys, time
import json
import argparse
import glob

# Parse commandline arguments
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", type=int, default=300, help="results waiting timeout in sec, default 300")
parser.add_argument('--verbose', '-v', action='count', default=0,
    help="show failed tests names and failure messages (-vv)")
parser.add_argument("path", type=str, help="path to selenium test")
args = parser.parse_args()
path = args.path
timeout = abs(args.timeout)
verbose = args.verbose
os.chdir(path)

# Count projects for results observe
projects = []
for side in glob.glob(path + '/sides/*.side'):
    side_file = open(side,'r')
    side_json = json.loads(side_file.read())
    side_file.close()
    if side_json['name'] in projects:
        print("Error: duplicated project names! Check input side files.")
        sys.exit(3)
    projects.append(side_json['name'])
projectsNb = len(projects)

# Remove old result json files
for result in glob.glob(path + '/out/*.json'):
    os.remove(result)

# Start selenium docker container
client = docker.from_env()
container = client.containers.run("opsdis/selenium-chrome-node-with-side-runner", auto_remove=True, shm_size="2G",
                                  volumes={ path + '/out': {'bind': '/selenium-side-runner/out', 'mode': 'rw'},
                                            path + '/sides': {'bind': '/sides', 'mode': 'rw'}}, detach=True)

# Wait for result file to be written
waitedfor = 0
while len(glob.glob(path + '/out/*.json')) < projectsNb and waitedfor <= timeout:
    time.sleep(1)
    waitedfor += 1

# Stop and remove container
container.stop()

# If no result was received after timeout exit with status unknown
if waitedfor >= timeout:
    print("UNKNOWN: Test timed out. Investigate issues.")
    sys.exit(3)

# Parse result files
times = { 'startTime': 0, 'endTime': 0 }
json_input = { 'numPassedTests': 0, 'numFailedTests': 0, 'numTotalTests': 0 }
failed = {}
for result in glob.glob(path + '/out/*.json'):
    file = open(result,'r')
    jsonResult = json.loads(file.read())
    file.close()
    if times['startTime'] == 0 or times['startTime'] > jsonResult['startTime']:
        times['startTime'] = jsonResult['startTime']
    for par in json_input.keys():
        json_input[par] += jsonResult[par]
    for testResult in jsonResult['testResults']:
        if times['endTime'] < testResult['endTime']:
            times['endTime'] = testResult['endTime']
        for aResult in testResult['assertionResults']:
            if aResult['status'] == 'failed':
                failed[aResult['fullName']] = aResult['failureMessages']

# Calculate execution time
exec_time = 0 if times['endTime'] <= times['startTime'] else \
    int(str(times['endTime'] - times['startTime'])[:-3])

# Exit logic with performance data
if json_input['numFailedTests'] == 0:
    print("OK: Passed " + str(json_input['numPassedTests']) + " of " + str(json_input['numTotalTests']) +
          " tests. | 'passed'=" + str(json_input['numPassedTests']) + ";;;; 'failed'=" +
          str(json_input['numFailedTests']) + ";;;; " + "'exec_time'=" + str(exec_time) + "s;;;;")
    sys.exit(0)

elif json_input['numFailedTests'] > 0:
    print("CRITICAL: Failed " +str(json_input['numFailedTests']) + " of " + str(json_input['numTotalTests']) +
          " tests" + ('.' if verbose == 0 else ": " +  ', '.join(failed.keys()) + '.' ) +
          " | 'passed'=" + str(json_input['numPassedTests']) + ";;;; 'failed'=" + str(json_input['numFailedTests']) +
          ";;;; " + "'exec_time'=" + str(exec_time) + "s;;;;")
    if verbose > 1:
        for testName in failed:
            print('TEST: ' + testName + '\n\n' + '\n\n'.join(failed[testName]))
    sys.exit(2)

else:
    print("UNKNOWN: Investigate issues")
    sys.exit(3)
