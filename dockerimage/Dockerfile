FROM selenium/standalone-chrome:4.1.1-20211217
#FROM selenium/standalone-chrome:3.141.59-xenon

LABEL maintainer="Opsdis Consulting AB <info@opsdis.com>"

# selenium container leaves us as user 'seluser', but we need to install more stuff
USER root

# Install nodejs LTS which includes npm
RUN apt-get -qqy update \
  && curl -sL https://deb.nodesource.com/setup_lts.x | sudo -E bash - \
  && apt-get -qqy --no-install-recommends install \
    nodejs \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

RUN npm install -g selenium-side-runner

RUN mkdir /sides && chown -R seluser /sides
VOLUME [ "/sides" ]

RUN mkdir /selenium-side-runner && chown -R seluser /selenium-side-runner
WORKDIR /selenium-side-runner

# Five seconds after starting container (as deamon) selenium-side-runner will run every /sides/*.side file
#RUN sed -i "/^\/usr\/bin\/supervisord.*/a \
#OPTS=('-c browserName=chrome --server http://localhost:4444/wd/hub' '--output-directory /selenium-side-runner/out')\n\
#[[ -s /sides/.options ]] && readarray -t -O 2 OPTS < /sides/.options\n\
#[[ -s /sides/.side.yml ]] && OPTS+=('--config /sides/.side.yml')\n\
#sleep 5 && selenium-side-runner \${OPTS[@]} /sides/*.side &> /selenium-side-runner/out/output.log" \
#/opt/bin/entry_point.sh

# Five seconds after starting container (as deamon) selenium-side-runner will run every /sides/*.side file
ENV GRID_FQDN=localhost
ENV GRID_PORT=4444
ENV GRID_PROTO=http
RUN sed -i "/^\/usr\/bin\/supervisord.*/a \
OPTS=('-c browserName=chrome')\n\
[[ -s /sides/.options ]] && readarray -t -O 2 OPTS < /sides/.options\n\
[[ -s /sides/.side.yml ]] && OPTS=('--config /sides/.side.yml')\n\
[ \"\$GRID_FQDN\" == \"localhost\" ] && sleep 5 && selenium-side-runner \${OPTS[@]} --server \$GRID_PROTO://\$GRID_FQDN:\$GRID_PORT/wd/hub --output-directory /selenium-side-runner/out /sides/*.side &> /selenium-side-runner/out/output.log \n\
[ \"\$GRID_FQDN\" == \"localhost\" ] || selenium-side-runner \${OPTS[@]} --server \$GRID_PROTO://\$GRID_FQDN:\$GRID_PORT/wd/hub --output-directory /selenium-side-runner\
/out /sides/*.side &> /selenium-side-runner/out/output.log" \
/opt/bin/entry_point.sh
RUN sed -i "s/^\/usr\/bin\/supervisord/\[ \"\$GRID_FQDN\" == \"localhost\" ] \&\& \/usr\/bin\/supervisord/" /opt/bin/entry_point.sh

USER seluser
