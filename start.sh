#!/bin/bash

run_process() {
    echo "Starting $1..."
    ./$1
}

run_process "web_prod.sh" &
run_process "rund_prod.sh" &

# Ждем завершения любого из процессов
wait -n

# Если один из процессов завершился, завершаем и второй
pkill -P $$ 