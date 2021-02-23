#!/bin/bash

function file_ends_with_newline() {
    [[ $(tail -c1 "$1" | wc -l) -gt 0 ]]
}

function append_newline(){
    if ! file_ends_with_newline $1
    then
        echo "" >> $1
        echo "New line appended to $1"
    fi
}

FILES=$(find . -type f -regex '.*\(in\|out\)$')
for f in $FILES; do
    append_newline $f
done
