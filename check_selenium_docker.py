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
import os, sys, time, traceback, signal
import json
import argparse
import glob
import re

# catch-all for exceptions exit codes
# @see https://nagios-plugins.org/doc/guidelines.html#AEN78
def except_hook(exctype, exc, tb):
    print('{}: {}'.format(type(exc).__name__, exc))
    traceback.print_exception(exctype, exc, tb)
    sys.exit(3)
sys.excepthook = except_hook

# Parse commandline arguments
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='count', default=0,
                    help="show failed test names and failure messages (-vv)")
parser.add_argument("--debug", type=str, default="false",
                    help="expose 4444 and 7900 ports of the container to the localhost to share screen/browser view, default 'false', other possible options: 'true'")
parser.add_argument("--timeout", type=int, default=300,
                    help="results waiting timeout in sec, default 300")
parser.add_argument("--browser", type=str, default="chrome",
                    help="container version to use, default 'chrome', other possible options: 'firefox' or 'edge'")
parser.add_argument("--gridproto", type=str, default="http",
                    help="selenium grid protocol to use, default 'http', other possible option: 'https'")
parser.add_argument("--gridfqdn", type=str, default="localhost",
                    help="selenium grid server to use, default 'localhost', other possible options: 'fqdn of your selenium grid server'")
parser.add_argument("--gridport", type=str, default="4444",
                    help="selenium grid server port to use, default '4444', other possible options: 'port of your selenium grid server'")
parser.add_argument('--no-newlines', action='store_true',
                    help="print newlines literally on multiline output")
parser.add_argument("path", type=str, help="path to selenium test")
args = parser.parse_args()
path = args.path
browser = args.browser
gridproto = args.gridproto
gridfqdn = args.gridfqdn
gridport = args.gridport
timeout = abs(args.timeout)
verbose = args.verbose
debug = args.debug
os.chdir(path)
if browser not in ['chrome', 'firefox', 'edge']:
    print("Error: not allowed browser!")
    sys.exit(3)

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
if projectsNb == 0:
    print("Error: no valid input side files found!")
    sys.exit(3)

# Remove old result json files
for result in glob.glob(path + '/out/*.json'):
    os.remove(result)

# Signal trap for container cleaning.
def handler(signum, frame):
    if 'container' in globals():
        container.stop()
    print("Error: execute interrupted!")
    sys.exit(3)
for sig in [signal.SIGTERM, signal.SIGINT]:
    signal.signal(sig, handler)

# Start selenium docker container
client = docker.from_env()
ports = {}
if debug == "true":
    ports = {'4444/tcp': 4444, '7900/tcp': 7900}
container = client.containers.run(
    'opsdis/selenium-' + browser + '-node-with-side-runner',
    auto_remove = True,
    shm_size = '2G',
    volumes = {
        path + '/out': { 'bind': '/selenium-side-runner/out', 'mode': 'rw' },
        path + '/sides': { 'bind': '/sides', 'mode': 'rw' },
    },
    environment={'GRID_FQDN':gridfqdn, 'GRID_PORT':gridport, 'GRID_PROTO':gridproto},
    ports = ports,
    detach = True
)

# Wait for result file to be written
waitedfor = 0
while len(glob.glob(path + '/out/*.json')) < projectsNb and waitedfor <= timeout:
    time.sleep(1)
    waitedfor += 1

# Stop and remove container
try:
    container.stop()
except docker.errors.APIError as err:
    pass

# If no result was received after timeout exit with status unknown
if waitedfor >= timeout:
    print("UNKNOWN: Test timed out. Investigate issues.")
    sys.exit(3)

# Parse result files
times = { 'startTime': 0, 'endTime': 0 }
json_input = { 'num' + i: 0 for i in
    [ 'FailedTestSuites', 'PassedTests', 'FailedTests', 'TotalTests']
}
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
    int(round(float(times['endTime'] - times['startTime'])/1000))

# Performace Data
perfData = ("'passed'={1};;{0}:;0;{0} 'failed'={2};;~:0;0;{0} 'exec_time'={3}s"
    ';;;;').format(json_input['numTotalTests'], json_input['numPassedTests'],
                   json_input['numFailedTests'], exec_time)
# Perf data from console output
# @see https://nagios-plugins.org/doc/guidelines.html#THRESHOLDFORMAT
def outOfRange(val, thre):
    val = float(val)
    if ':' not in thre:
        return val < 0 or val > float(thre)
    thre = thre.split(':')
    if thre[0] == '~':
        return val > float(thre[1])
    if thre[1] == '':
        return val < float(thre[0])
    if '@' in thre[0]:
        return val >= float(thre[0].replace('@', '')) and val <= float(thre[1])
    return val < float(thre[0]) or val > float(thre[1])

statusCode = 0
exitStatus = ['OK', 'WARNING', 'CRITICAL']
# [warn, crit]
alerts = [[], []]
if os.path.isfile(path + '/out/output.log'):
    perfDataReg = ("PERFDATA: '?([^=']+[^' ])'? *= *"
                   "((-?[0-9]+(\.[0-9]+)?|U)[^\d';]*(;.*)*)\n$")
    # [threshold, min/max]
    validators = [
        re.compile('^(~|@?[0-9]+(\.[0-9]+)?)(:|:[0-9]+(\.[0-9]+)?)?$'),
        re.compile('^[0-9]+(\.[0-9]+)?$'),
    ]
    file = open(path + '/out/output.log','r')
    for perf in re.findall(perfDataReg, file.read(), flags=re.MULTILINE):
        perfVals = perf[1].split(';')
        perfValid = True
        # validate thresholds and min/max fields
        for id in range(1,5):
            if len(perfVals) > id and perfVals[id] != '' \
                    and not validators[0 if id < 3 else 1].match(perfVals[id]):
               perfValid = False
        if len(perfVals) > 5 or not perfValid:
            continue
        # compare value with crit and warn thresholds
        for id in [2, 1]:
            if perf[2] != 'U' and len(perfVals) > id and perfVals[id] != '' \
                    and outOfRange(perf[2], perfVals[id]):
                if statusCode < id:
                    statusCode = id
                # do not put warn alert if crit exits
                if id != 1 or perf[0] not in alerts[1]:
                    alerts[id - 1].append(perf[0])
        perfData += " '{}'={}".format(*perf)
    file.close()

def getAlertsInfo():
    alertsInfo = [
        '{} critical and {} warning alerts.'.format(*map(len, reversed(alerts)))
    ]
    if verbose > 0:
        for idx, val in enumerate(alerts):
            if len(val) > 0:
                alertsInfo.append('{}: {}.'.format(exitStatus[idx + 1].title(),
                    ', '.join(val)))
    return ' '.join(alertsInfo)

# Exit logic with performance data
if json_input['numFailedTestSuites'] == 0 and json_input['numFailedTests'] == 0:
    print('{}: Passed {} of {} tests'.format(exitStatus[statusCode],
            json_input['numPassedTests'], json_input['numTotalTests']) +
       ('.' if statusCode == 0 else ' with ' + getAlertsInfo()) +
       " | " + perfData)
    sys.exit(statusCode)

elif json_input['numFailedTests'] > 0:
    print('CRITICAL: Failed {} of {} tests'.format(json_input['numFailedTests'],
            json_input['numTotalTests']) +
      ('.' if verbose == 0 else ": " +  ', '.join(failed.keys()) + '.' ) +
      ('' if not sum(map(len, alerts)) else ' ' + getAlertsInfo()) +
      " | " + perfData, end = '')
    if verbose > 1:
        for testName in failed:
            output = '\nTEST: ' + testName + '\n' + '\n\n'.join(failed[testName])
            print(output.replace('\n', '\\n') if args.no_newlines else output,
                  end = '')
    print('')
    sys.exit(2)

else:
    print("UNKNOWN: Investigate issues")
    sys.exit(3)
