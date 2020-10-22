#!/usr/bin/env python3

import csv
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument( 'csv_filename' )
args = parser.parse_args()

filename = args.csv_filename
csvfile = open( filename, 'r' )
reader = csv.reader( csvfile, delimiter=',' )

for alumne, repo in reader :
    alumne = alumne.split()
    nom = ".".join([alumne[i] for i in [0,2]])
    
    repo = repo.replace("https://gitlab.com/", "git@gitlab.com:")

    print(nom, " => ", repo)
    if repo:
        subprocess.call(["git", "clone", repo, nom])
