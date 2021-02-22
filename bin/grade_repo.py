#!/usr/bin/env python3.8
import argparse
import yaml
import subprocess
from glob import glob
import os
from threading import Timer
import difflib
import itertools
from colorama import Fore
import re
from datetime import datetime
import sys

def loadYAML( filename ) :
    with open(filename, 'r') as stream: 
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)

def column_print(first, second):
    ansi_escape = r'\x1b\[\d{1,2}m'
    def get_nchars(string):
        """Return number of characters, omitting ANSI codes."""
        ansi_pattern = re.compile( ansi_escape )
        return len(ansi_pattern.sub('', string))

    first = first.splitlines()
    second = second.splitlines()
    for i, j in itertools.zip_longest(first, second):
        i = "^"+i+"$" if i != None else ""
        j = "^"+j+"$" if j != None else ""
        print("    {}{}    {}{}".format(i, " "*(50 - get_nchars(i)), j, " "*(50 - get_nchars(j))))

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument( "test_cases" )
    parser.add_argument( "dir", nargs="*" )
    args = parser.parse_args()

    args.dir.sort(key=lambda x: x.split(".")[1])

    for path_dir in args.dir:
        tag_command = "git -C {} checkout master".format(path_dir)
        code_tag = subprocess.call(tag_command.split())
        pull_command = "git -C {} pull --tags".format(path_dir)
        print(pull_command)
        code_pull = subprocess.call(pull_command.split())
        print()

        if code_pull != 0:
            continue

        test_cases = loadYAML( args.test_cases )

        subpackage = test_cases["subPackage"]
        tag = test_cases.get("tag", "master")
        tag_command = "git -C {} checkout {}".format(path_dir, tag)
        print(tag_command)
        code_tag = subprocess.call(tag_command.split())
        print()

        if code_tag != 0:
            print("Error al canviar al tag {}".format(tag))
            continue

        tagdate_command = "git -C {} log -1 --format=%ai {}".format(path_dir, tag)
        process = subprocess.Popen(tagdate_command.split(), stdout=subprocess.PIPE)
        tag_date = " ".join(process.communicate()[0].decode("utf-8").strip().split()[:-1])
        tag_date = datetime.fromisoformat(tag_date)
        test_date = datetime.fromisoformat(test_cases["date"])
        print(tag_date, test_date)
        if tag_date > test_date:
            print("El tag ha segut modificat despres de la data d'entrega")
            continue

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
                 
            subprocess.call(["cat", "-n", source_file])
            print()

            # Build
            compile_command = "docker run --rm -v {}/{}:/app -w /app -i java:alpine javac -cp out/ -sourcepath src/ -d out/ src/{}.java".format(os.getcwd(), path_dir, package)
            return_code = subprocess.call(compile_command.split())
            if return_code != 0 :
                 print("Error compiling: {}.java".format(name))
                 continue

            for test in exercise.get("tests",[]) :
                expected_output = test["output"]
                test_input = test["input"]

                status = None
                process = subprocess.Popen("docker run --rm -v {}/{}:/app -w /app -i java:alpine java {}".format(os.getcwd(), out_dir, package).split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                timer = Timer(5, process.kill)
                try :
                    timer.start()
                    output = process.communicate(input=test_input.encode('utf-8'))[0].decode("utf-8")
                    return_code = process.returncode
                except Exception : 
                    status = "TIMEOUT"
                finally :
                    timer.cancel()


                expected_output += '\n'
                diffcodes = difflib.SequenceMatcher(a=expected_output, b=output).get_opcodes()

                # print(diffcodes)
                
                color_expected_output = ""
                color_output = ""
                if not status:
                    if return_code != 0:
                        status = Fore.RED + "RUNTIME" + Fore.RESET
                    elif len(output) == 0 :
                        status = Fore.RED + "EMPTY" + Fore.RESET
                    else :
                        perfect = True
                        presentation = False
                        failed = False

                        for diff, ia, ja, ib, jb in diffcodes :

                            expected_color = None
                            output_color = None

                            if diff == "insert" :
                                perfect = False

                                if ia < ja:
                                    failed = True

                                if ib < jb:
                                    if output[ib:jb].strip() == "":
                                        presentation = False
                                    else :
                                        output_color = Fore.YELLOW

                            elif diff == "replace" :
                                perfect = False
                                failed = True
                                expected_color = Fore.RED
                                output_color = Fore.RED

                            elif diff == "delete" :
                                perfect = False
                                failed = True

                            elif diff == "equal" :
                                expected_color = Fore.GREEN
                                output_color = Fore.GREEN

                            if expected_color:
                                color_expected_output += "\n".join(expected_color + s + Fore.RESET if len(s) > 0 else s for s in expected_output[ia:ja].split("\n"))
                            else :
                                color_expected_output += expected_output[ia:ja]
                            if output_color:
                                color_output += "\n".join(output_color + s + Fore.RESET if len(s) > 0 else s for s in output[ib:jb].split("\n"))
                            else:
                                color_output += output[ib:jb]

                        # color_expected_output = color_expected_output.replace(Fore.RESET, "RESET")
                        # color_expected_output = color_expected_output.replace(Fore.YELLOW, "YELLOW")
                        # color_expected_output = color_expected_output.replace(Fore.RED, "RED")
                        # color_expected_output = color_expected_output.replace(Fore.GREEN, "GREEN")
                        # color_output = color_output.replace(Fore.RESET, "RESET")
                        # color_output = color_output.replace(Fore.YELLOW, "YELLOW")
                        # color_output = color_output.replace(Fore.RED, "RED")
                        # color_output = color_output.replace(Fore.GREEN, "GREEN")

                        if perfect :
                            status = Fore.GREEN + "PERFECT" + Fore.RESET
                        elif failed:
                            status = Fore.RED + "FAILED" + Fore.RESET
                        elif presentation :
                            status = Fore.CYAN + "PRESENTATION" + Fore.RESET
                        else :
                            status = Fore.YELLOW + "PASSED" + Fore.RESET

                print("- {}: {}".format(test["name"], status))
                print("- input")
                print("\t" + test_input.replace("\n", "\t\n"))
                print("- output")
                column_print(color_expected_output, color_output)
                print()
        tag_command = "git -C {} checkout master".format(path_dir)
        code_tag = subprocess.call(tag_command.split())
        print("=================================")
