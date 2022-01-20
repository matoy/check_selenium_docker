check_selenium_docker
-----------------------

- [Overview](#overview)
  * [Highlights](#highlights)
- [Workflow](#metrics-naming)
- [System requirements](#system-requirements)
- [Docker image](#docker-image)
- [Plugin](#plugin)
- [Add new test scenarios](#add-new-test-scenarios)
- [Execute the plugin](#execute-the-plugin)
- [Performance metrics](#performance-metrics)
- [License](#license)

# Overview #
Synthetic website monitoring with Selenium and Docker.

check_selenium_docker is a Nagios based plugin that spins up a Docker container, executes the test and, once the test is finished and the result has been reported back to the monitoring solution, removes the Docker container.

### Highlights ###

* Works with any Nagios compatible system such as Centreon. Centreon specific integration will be take in all examples below.
* Every test is executed in a fresh environment. (https://www.selenium.dev/documentation/en/guidelines_and_recommendations/fresh_browser_per_test/)
* Will remove the Docker container as soon as the test is complete. Requires no manual cleanup of stopped containers.
* Any custom performance metrics is allowed.

# Workflow #

Install Selenium IDE for Chrome (https://selenium.dev/downloads).

Record your test.

Export the test and copy the .side file to the server that will run the docker image.

A Docker container will execute the test and report the test results back to the monitoring system.

![Workflow](img/selenium_docker.png)

# System requirements #
The following prerequisites must be installed on the server that will execute the plugin.

* Python 3 with the docker module
* docker-ce

```
# Install docker-ce
yum install -y yum-utils \
  device-mapper-persistent-data \
  lvm2

yum-config-manager \
    --add-repo \
    https://download.docker.com/linux/centos/docker-ce.repo

yum install docker-ce

yum install python-pip3

# Add user 'centreon-engine' to group 'docker'
usermod -aG docker centreon-engine

# Start and enable docker
systemctl start docker && systemctl enable docker
service centreon restart

# Install the docker Python 3 module
pip-3 install docker

# (Optional) Add versionlock to docker-ce
yum install yum-plugin-versionlock
yum versionlock docker-ce

# (Optional) Remove versionlock from docker-ce
yum versionlock clear
```


# Docker image #

Build the Docker image:

```
git clone https://github.com/matoy/check_selenium_docker
cd check_selenium_docker/dockerimage/

# eventually add --build-arg http_proxy=http://yourproxyfqdn:port/ if required
docker build . --tag opsdis/selenium-chrome-node-with-side-runner --no-cache
```

Image for an alternative supported browser:

```
# eventually add --build-arg http_proxy=http://yourproxyfqdn:port/ if required
sed 's/chrome/firefox/' Dockerfile | docker build --tag opsdis/selenium-firefox-node-with-side-runner -

# eventually add --build-arg http_proxy=http://yourproxyfqdn:port/ if required
docker build . -f Dockerfile-Edge --tag opsdis/selenium-edge-node-with-side-runner

cd ..
```

# Plugin #

Copy the plugin to the plugin directory and make it executable:

```
cp check_selenium_docker.py /usr/lib/centreon/plugins/
chmod +x /usr/lib/centreon/plugins/check_selenium_docker.py
```

Add a new check_command to Monitor:

```
check_selenium_docker
$USER1$/custom/check_selenium_docker.py $ARG1$
```


# Add new test scenarios #

Create a new main directory (/opt/plugins/custom/selenium) in the main directory create a new directory 
preferably named as the URL used in the test (/opt/plugins/custom/selenium/opsdis.com):

```
mkdir /usr/lib/centreon/plugins/selenium
mkdir /usr/lib/centreon/plugins/selenium/mysite.com
```

Create two subdirectories, out and sides:

```
mkdir /usr/lib/centreon/plugins/selenium/mysite.com/{out,sides}
```

Add the side-file to the sides subdirectory and modify the permissions:

```
chmod 777 /usr/lib/centreon/plugins/selenium/*/out/
chmod 755 /usr/lib/centreon/plugins/selenium/*/sides/*.side
```

Optionally add a runner local configuration file or additional command-line
arguments to pass, for example:

```
cat <<EOT > //usr/lib/centreon/plugins/selenium/mysite.com/sides/.options
--filter MyTestSuite
EOT

# to accept non trusted certs/CA
cat <<EOT > /usr/lib/centreon/plugins/selenium/mysite.com/sides/.side.yml
capabilities:
  browserName: chrome
  acceptInsecureCerts: true
EOT

# to make the browser use a specific proxy
cat <<EOT > /usr/lib/centreon/plugins/selenium/mysite.com/sides/.side.yml
capabilities:
  browserName: chrome
proxyType: manual
proxyOptions:
  http: http://proxyfqdn:port
  https: http://proxyfqdn:port
EOT

# to use headless feature of the browser
cat <<EOT > /usr/lib/centreon/plugins/selenium/mysite.com/sides/.side.yml
capabilities:
  browserName: chrome
  chromeOptions:
    args:
      - headless
EOT
```

See [Command-line Runner / Run-time configuration](https://www.selenium.dev/selenium-ide/docs/en/introduction/command-line-runner#run-time-configuration).

The directory structure should look like this:

```
├── opsdis.com
│   ├── out
│   └── sides
│       └── opsdis.com.side
│       └── .side.yml
│       └── .options
```

# Execute the plugin #

```
/usr/lib/centreon/plugins/check_selenium_docker.py /usr/lib/centreon/plugins/selenium/mysite.com
OK: Passed 2 of 2 tests. | 'passed'=2;;2:;0;2 'failed'=0;;~:0;0;2 'exec_time'=6s;;;;

# other examples:
# with Edge browser instead of Chrome
/usr/lib/centreon/plugins/check_selenium_docker.py /usr/lib/centreon/plugins/selenium/mysite.com --browser=edge

# with another existing grid server, for example located geographically elsewhere
/usr/lib/centreon/plugins/check_selenium_docker.py /usr/lib/centreon/plugins/selenium/mysite.com --gridproto https --gridfqdn mygridserver --gridport 443
```

# Performance metrics #

Console output (Selenium IDE `echo` command) is parsed for additional custom
metrics marked with  `PERFDATA: ` prefix and guidelines compliant expression
for [Performance data](https://nagios-plugins.org/doc/guidelines.html#AEN200),
i.e., `PERFDATA: First Response Time = ${calculatedTime}s;120` could give for 
`calculatedTime = 150` (as a results of `exec script` SIDE command):

```
/usr/lib/centreon/plugins/check_selenium_docker.py -vv /usr/lib/centreon/plugins/selenium/mysite.com
WARNING: Passed 2 of 2 tests with 0 critical and 1 warning alerts. Warning: First Response Time. | 'passed'=2;;2:;0;2 'failed'=0;;~:0;0;2 'exec_time'=6s;;;; 'First Response Time'=150s;120
```

# Debug 
You can execute the script with the --debug true parameter ; this will result the docker container to be executing with exposing its 4444 & 7900 ports:
```
/usr/lib/centreon/plugins/check_selenium_docker.py /usr/lib/centreon/plugins/selenium/my-site.com/ --browser chrome --timeout 60 -vv --debug true
```
Then connect to the 7900 port of your host running the script with a browser, you'll get the VNC interface (password is secret by default) and see what is being made in the browser.

You can go further by getting output inside the container itself bypassing the python script:
```
export testfolder=/usr/lib/centreon/plugins/selenium/mysite.com
export image=opsdis/selenium-chrome-node-with-side-runner
docker run -it --rm -p 4444:4444 -p 7900:7900 --shm-size="2g" -v $testfolder/sides:/sides -v $testfolder/out:/selenium-side-runner/out $image /opt/bin/entry_point.sh
```
This will also allow you to connect to the selenium web interface (on port 4444) and VNC (on port 7900, pass: secret) to look at the executing scenario in the browser.

# License 
check_selenium_docker is licensed under GPL version 3.
