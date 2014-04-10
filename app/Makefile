SHELL := $(shell which bash)
ACTIVATE_VENV = source venv/bin/activate
SUPERVISORD_CMD = ${ACTIVATE_VENV} && supervisord -c supervisord.conf
SUPERVISORCTL_CMD = ${ACTIVATE_VENV} && supervisorctl
ARCHIVE_FILE = ./archive/$(shell date +'%y%m%d.%H%M%S').tar.bz2
ENV ?= local

.PHONY: $(PHONY) all setup status test clean clobber venv


all:
	$(error Please pick a target)

setup: requirements.txt | logs
	@cp configs/config_${ENV}.py configs/config_override.py
	@virtualenv venv
	@${ACTIVATE_VENV} && pip install -r $<

clean:
	@echo "deleting pyc files, pep8.out, pylint.out and nosetests.xml"
	@find test -type f -name "*.pyc" | xargs rm -f
	@rm -f *.pyc
	@rm -f $(LOCAL_ROOT)/pep8.out $(LOCAL_ROOT)/pylint.out ./nosetests.xml

clobber: clean
	@echo "venv, log and storage directories"
	@rm -rf  venv
	@rm -rf storage
	@rm -rf logs
	@rm -rf configs/config_override.py

logs logs/archive:
	@mkdir -p $@

archive: | logs logs/archive
	@cd logs && tar cjf ${ARCHIVE_FILE} --exclude archive *
	@find logs -maxdepth 1 -name archive -prune -o -type f -exec rm -f {} \;

import: | venv
	#${ACTIVATE_VENV} && python import_script.py

start: logs archive ${VIRTUALENV}
	@if [ -f supervisord.pid ]; then \
		echo "app already running with pid of `cat supervisord.pid`" && make status; \
	else \
		${SUPERVISORD_CMD}; \
	fi

reload: start
	${SUPERVISORCTL_CMD} reload

stop: status
	@if [ ! -f supervisord.pid ]; then \
		echo "app is not running"; \
	else \
		echo "killing `cat supervisord.pid`" && cat supervisord.pid | xargs kill; \
	fi

status:
	${SUPERVISORCTL_CMD} status