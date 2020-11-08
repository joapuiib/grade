#!/usr/bin/env python3
import argparse
import yaml
import subprocess
from glob import glob
import os
from shutil import copyfile

parser = argparse.ArgumentParser()
parser.add_argument( "test_cases" )
parser.add_argument( "dir", nargs="+" )
parser.add_argument( "--dry", default=False, action="store_true" )
parser.add_argument( "-v", "--verbose", default=False, action="store_true")
args = parser.parse_args()

def loadYAML( filename ) :
    with open(filename, 'r') as stream: 
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)

args.dir.sort(key=lambda x: x.split(".")[1])

for path_dir in args.dir:
    pull_command = "git -C {} pull".format(path_dir)
    if args.verbose or args.dry:
        print(pull_command)
    if not args.dry:
        code_pull = subprocess.call(pull_command.split())

    if not args.dry and code_pull is not 0:
        continue

    test_cases = loadYAML( args.test_cases )

    subpackage = test_cases["subPackage"]
    for exercise in test_cases["exercises"]:
        name = exercise["className"]
        path = "{}/**/{}/{}.java".format(path_dir, "/".join(subpackage.split(".")), name)
        source_file = next(iter(glob(path, recursive=True)), None)

        print(source_file)
        if not source_file :
            print("{}: Not found".format(name))
            continue

        package = source_file.split("src/")[1].replace(".java","")

        out_dir = "{}/out/".format(path_dir)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
             
        # Build
        compile_command = "docker run --rm -v {}/{}:/app -w /app -i java:alpine javac -d out/ src/{}.java".format(os.getcwd(), path_dir, package)
        if args.verbose or args.dry:
            print(compile_command)
        if not args.dry:
            returncode = subprocess.call(compile_command.split())
            if returncode != 0 :
                print("Error compiling: {}.java".format(name))
                continue

            subprocess.call(["cat", source_file])
            print()

            for test in exercise["tests"] :
                test_input = test["input"]
                test_output = test["output"]
                # Run
                process = subprocess.Popen("docker run --rm -v {}/{}:/app -w /app -i java:alpine java {}".format(os.getcwd(), out_dir, package).split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                output = process.communicate(input=test_input.encode('utf-8'))[0].decode("utf-8")
                if process.returncode != 0:
                    status = "RUNTIME"
                elif len(output) == 0 :
                    status = "EMPTY"
                elif output[-1] != "\n" :
                    status = "NEW_LINE"
                else :
                    output = output.strip()
                    if output == test_output :
                        status = "PERFECT"
                    elif test_output in output :
                        status = "PASSED"
                    else :
                        status = "FAILED"
                print("- {:15}: {:8} input: \"{}\" expected_output: \"{}\" output: \"{}\"".format(test["name"], status, \
                    test_input.replace("\n","\\n"), test_output.replace("\n","\\n"), output.replace("\n","\\n")))
            print()
    print("=================================")
