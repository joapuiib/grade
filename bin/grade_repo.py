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
from ansiwrap import wrap
from pygments import highlight as highlight_py
from pygments.lexers import get_lexer_by_name
from pygments.formatters import Terminal256Formatter


def highlight(text):
    return highlight_py(text, get_lexer_by_name("java"), Terminal256Formatter(style="monokai"))


def line_number_print(text):
    for i, line in enumerate(text.split("\n")):
        print("{0: 8}  {1:}".format(i + 1, line))


def loadYAML(filename):
    with open(filename, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)


def remove_color(string):
    ansi_escape = r'\x1b\[(?:\d;)?\d{1,2}m'
    ansi_pattern = re.compile(ansi_escape)
    return ansi_pattern.sub('', string)


def column_print(first, second, n=40):
    margin = 10
    space = n + margin

    def get_nchars(string):
        return len(remove_color(string))

    first = first.splitlines()
    second = second.splitlines()
    for i, j in itertools.zip_longest(first, second):
        i = "^" + i + "$" if i is not None else ""
        j = "^" + j + "$" if j is not None else ""
        i_list = wrap(i, n)
        j_list = wrap(j, n)
        for ii, jj in itertools.zip_longest(i_list, j_list):
            ii = ii if ii is not None else ""
            jj = jj if jj is not None else ""
            print("    {}{}    {}{}".format(ii, " " * (space - get_nchars(ii)), jj, " " * (space - get_nchars(jj))))


def load_file(path):
    with open(path, "r") as f:
        content = f.read()
        if content.endswith("\n"):
            content = content[:-1]
        return content


def load_tests(path):
    tests_path = path + "/tests"
    tests = []
    if os.path.isdir(tests_path):
        filenames = set()
        for name in os.listdir(tests_path):
            name, _ = os.path.splitext(name)
            filenames.add(name)

        for name in filenames:
            file_path = "{}/{}".format(tests_path, name)
            if os.path.isfile(file_path + ".in") and os.path.isfile(file_path + ".out"):
                entrada = load_file(file_path + ".in")
                sortida = load_file(file_path + ".out")
                tests += [{"name": name, "input": entrada, "output": sortida}]
            else:
                break

    return tests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("test_cases")
    parser.add_argument("dir", nargs="*")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--remove-color", action="store_true")
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("-v", "--volume", action="append", default=[])
    args = parser.parse_args()

    args.dir.sort(key=lambda x: x.split(".")[1])

    for path_dir in args.dir:
        tag_command = f"git -C {path_dir} checkout master"
        code_tag = subprocess.call(tag_command.split())
        pull_command = f"git -C {path_dir} pull --tags -f"
        print(pull_command)
        code_pull = subprocess.call(pull_command.split())
        print()

        if code_pull != 0:
            continue

        test_cases = loadYAML(args.test_cases)

        package = test_cases["package"]
        tag = test_cases.get("tag", "master")
        tag_command = f"git -c advice.detachedHead=false -C {path_dir} checkout {tag}"
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
        print("Limit:", test_date, "Submitted:", tag_date)
        if tag_date > test_date:
            print(Fore.RED + "COMPTE!! El tag ha segut modificat despres de la data d'entrega" + Fore.RESET)

        out_dir = "{}/out/".format(path_dir)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        volumes = args.volume
        volumes += test_cases.get("volumes", [])

        for exercise in test_cases.get("exercises", []):
            name = exercise["className"]
            subpackage = exercise.get("subpackage", "")
            path = "{}/**/{}/{}.java".format(path_dir, "/".join(package.split(".")), "/".join([subpackage, name]))

            print("=" * 20)
            print(name)
            print(path)
            print("=" * 20)

            source_file = next(iter(glob(path, recursive=True)), None)

            if not source_file:
                print("{}: Not found".format(name))
                continue

            java_package = source_file.split("src/")[1].replace(".java", "")

            tests = exercise.get("tests", [])
            tests += load_tests(f"testcases/problems/{name}")

            # Build
            compile_command = f"docker run --rm -v {os.getcwd()}/{path_dir}:/app -w /app -i openjdk:12 javac -verbose -cp out/ -sourcepath src/ -d out/ src/{java_package}.java"
            print(compile_command)

            process = subprocess.Popen(compile_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            err_compile, out_compile = map(lambda x: x.decode("utf-8"), process.communicate())
            # print("OUT", out_compile)
            # print("ERR", err_compile)
            return_code = process.returncode

            if return_code != 0:
                print("Error compiling: {}.java".format(name))
                continue

            # Look for sources in compile output and print them
            matches = re.findall(r"out/([^$\n]*)\.class", out_compile)
            # print(out_compile)
            # print(matches)

            for source in matches:
                source_file = "{}/src/{}.java".format(path_dir, source)
                print(source_file)
                with open(source_file) as f:
                    line_number_print(highlight(f.read()))
                print()

            volumes_str = " ".join([f"-v {os.getcwd()}/{path_dir}/{volume_name}:/app/{volume_name}" for volume_name in volumes])
            run_command = f"docker run --rm -v {os.getcwd()}/{out_dir}:/app {volumes_str} -w /app -i openjdk:12 java {java_package}"
            print(run_command)
            if args.interactive:
                try:
                    process = subprocess.Popen(run_command.split())
                    process.communicate()
                except KeyboardInterrupt:
                    print("\rProgram stopped.")
                continue

            for test in tests:
                expected_output = test["output"]
                test_input = test["input"]

                status = None
                process = subprocess.Popen(run_command.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                timer = Timer(5, process.kill)
                try:
                    timer.start()
                    output = process.communicate(input=test_input.encode('utf-8'))[0].decode("utf-8")
                    if args.remove_color:
                        output = remove_color(output).replace("\u001B", "\\u001B")
                    else:
                        output = output.replace("\u001B", "\\u001B")

                    return_code = process.returncode
                except Exception:
                    status = "TIMEOUT"
                finally:
                    timer.cancel()

                expected_output += '\n'
                diffcodes = difflib.SequenceMatcher(a=expected_output, b=output).get_opcodes()

                # print(diffcodes)

                color_expected_output = ""
                color_output = ""
                if not status:
                    if return_code != 0:
                        status = Fore.RED + "RUNTIME" + Fore.RESET
                    elif len(output) == 0:
                        status = Fore.RED + "EMPTY" + Fore.RESET
                    else:
                        perfect = True
                        presentation = False
                        failed = False

                        for diff, ia, ja, ib, jb in diffcodes:

                            expected_color = None
                            output_color = None

                            if diff == "insert":
                                perfect = False

                                if ia < ja:
                                    failed = True

                                if ib < jb:
                                    if output[ib:jb].strip() == "":
                                        presentation = False
                                    else:
                                        output_color = Fore.YELLOW

                            elif diff == "replace":
                                perfect = False
                                failed = True
                                expected_color = Fore.RED
                                output_color = Fore.RED

                            elif diff == "delete":
                                if not (expected_output[ia:ja].strip() and output[ib:jb].strip()):
                                    presentation = True
                                else:
                                    perfect = False
                                    failed = True

                            elif diff == "equal":
                                expected_color = Fore.GREEN
                                output_color = Fore.GREEN

                            if expected_color:
                                color_expected_output += "\n".join(expected_color + s + Fore.RESET if len(s) > 0 else s for s in expected_output[ia:ja].split("\n"))
                            else:
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

                        if failed:
                            status = Fore.RED + "FAILED" + Fore.RESET
                        elif presentation:
                            status = Fore.CYAN + "PRESENTATION" + Fore.RESET
                        elif perfect:
                            status = Fore.GREEN + "PERFECT" + Fore.RESET
                        else:
                            status = Fore.YELLOW + "PASSED" + Fore.RESET

                print("- {}".format(test["name"]))
                print("- input")
                for line in test_input.splitlines():
                    print(Fore.CYAN + "    {}".format(line) + Fore.RESET)
                print("- output")
                column_print(color_expected_output, color_output)
                print("- status: {}".format(status))
                print()

        # Remove out dir
        compile_command = f"docker run --rm -v {os.getcwd()}/{path_dir}:/app -w /app -i openjdk:12 rm -r out/"
        print(compile_command)
        process = subprocess.Popen(compile_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()

        tag_command = "git -C {} checkout master".format(path_dir)
        code_tag = subprocess.call(tag_command.split())
