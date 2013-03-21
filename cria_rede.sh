#!/bin/bash

echo 'Criando rede com' $1 'nós'

for ((i=0; i<$1; i++))
do
	
	porta=$((4000+$i))
	exec "./trab.py"  $porta &
	sleep 1
	echo "Nó $i criado na porta $porta"
done