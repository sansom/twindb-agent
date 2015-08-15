#!/usr/bin/env bash

set -eu

# Find path to twindb agent
TWINDB_ARGENT=""
for dir in `python -c "import sys; print ' '.join(x for x in sys.path if x)"`
do
    if test -f ${dir}/twindb_agent/__main__.py
    then
        TWINDB_ARGENT=${dir}/twindb_agent/__main__.py
        break
    fi
done

if test -z "${TWINDB_ARGENT}"
then
    echo "Can not find TwinDB agent module"
    exit
fi

# If no options given - print help
if test -z "$*"
then
    python ${TWINDB_ARGENT} --help
    exit
fi

PID_FILE=`python -c "import twindb_agent.globals; print(twindb_agent.globals.pid_file)"`


# If --stop option if given - kill the agent
for opt in $*
do
    if [ ${1} = "--stop" ]
    then
        if test -f "${PID_FILE}"
        then
            PID=`cat "${PID_FILE}"`
            WAIT_TIMEOUT=300
            WAIT_TIME=0
            kill ${PID}
            while kill -0 ${PID} 2> /dev/null
            do
                sleep 1
                if [ ${WAIT_TIME} -gt ${WAIT_TIMEOUT} ]
                then
                    echo "Agent didn't exit after ${WAIT_TIMEOUT} seconds. Killing it."
                    kill -9 ${PID}
                    rm -f "${PID_FILE}"
                    exit
                fi
                WAIT_TIME=$((WAIT_TIME + 1))
            done
            rm -f "${PID_FILE}"
            exit
        else
            echo "Pid file ${PID_FILE} does't exist"
            exit
        fi
        exit
    fi
done

# Check if another instance is running
if test -f "${PID_FILE}"
then
    echo "Pid file ${PID_FILE} exists"
    PID=`cat "${PID_FILE}"`
    if kill -0 ${PID}
    then
        # PID exists
        # check if it's an agent's PID
        if test -z "`grep twindb_agent/__main__.py /proc/${PID}/cmdline`"
        then
            # It's not agent's PID
            echo "Process ${PID} is not TwinDB agent"
            rm -f "${PID_FILE}"
        else
            # It's agent's PID. It's running
            echo "Another TwinDB agent is running"
            exit
        fi
    else
        echo "Removing abandoned pid file ${PID_FILE}"
        rm -f "${PID_FILE}"
    fi
fi

set +e
while true
do
    python ${TWINDB_ARGENT} $* &
    PID=$!
    echo ${PID} > "${PID_FILE}"
    wait ${PID}
    ret=$?
    rm -f "${PID_FILE}"
    if [ ${ret} -eq 0 ]
    then
        exit
    fi
    sleep 1
done
