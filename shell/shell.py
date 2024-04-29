#!/usr/bin/env python3

import os
import sys
import re

def print_prompt():
    ps1 = os.getenv("PS1", "$ ")
    print(ps1, end="", flush=True)

def execute_command(command):
    try:
        pid = os.fork()
        if pid == 0:  # Child process
            os.execvp(command[0], command)  # Changed execve to execvp for path resolution
        elif pid > 0:  # Parent process
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status) and os.WEXITSTATUS(status) != 0:
                print(f"Program terminated with exit code {os.WEXITSTATUS(status)}")
    except Exception as e:
        print(f"Error executing command {command[0]}: {str(e)}")
        sys.exit(1)

def find_command(command):
    if os.path.isabs(command[0]) and os.access(command[0], os.X_OK):
        return command
    paths = os.getenv("PATH", "").split(":")
    for path in paths:
        executable_path = os.path.join(path, command[0])
        if os.path.exists(executable_path) and os.access(executable_path, os.X_OK):
            command[0] = executable_path  # Update command with full path
            return command
    return command

def handle_input_redirection(command, input_file):
    try:
        pid = os.fork()
        if pid == 0:
            with open(input_file, 'r') as f:
                os.dup2(f.fileno(), sys.stdin.fileno())
                os.execvp(command[0], command)
        elif pid > 0:
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        return 1
    except Exception as e:
        print(f"Error: {str(e)}")

def handle_output_redirection(command, output_file):
    try:
        pid = os.fork()
        if pid == 0:
            with open(output_file, 'w') as f:
                os.dup2(f.fileno(), sys.stdout.fileno())
                os.execvp(command[0], command)
        elif pid > 0:
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
    except PermissionError:
        print(f"Error: Cannot write to output file '{output_file}'")
        return 1
    except Exception as e:
        print(f"Error: {str(e)}")

def handle_piping(command1, command2):
    try:
        pipe_read, pipe_write = os.pipe()
        pid1 = os.fork()
        if pid1 == 0:
            os.dup2(pipe_write, sys.stdout.fileno())
            os.close(pipe_read)
            os.close(pipe_write)
            os.execvp(command1[0], command1)
        elif pid1 > 0:
            os.close(pipe_write)
            pid2 = os.fork()
            if pid2 == 0:
                os.dup2(pipe_read, sys.stdin.fileno())
                os.close(pipe_read)
                os.execvp(command2[0], command2)
            elif pid2 > 0:
                os.close(pipe_read)
                _, status1 = os.waitpid(pid1, 0)
                _, status2 = os.waitpid(pid2, 0)
                if os.WIFEXITED(status1) and os.WIFEXITED(status2):
                    return os.WEXITSTATUS(status2)
    except Exception as e:
        print(f"Error in piping: {str(e)}")

def execute_background_task(command):
    try:
        pid = os.fork()
        if pid == 0:
            os.setsid()
            os.umask(0)
            try:
                os.execvp(command[0], command)  # Use execvp to use PATH for resolution
            except FileNotFoundError:
                sys.stderr.write(f"{command[0]}: command not found\n")
                sys.exit(1)
        else:
            print(f"[{pid}] Started in background")
            return pid
    except Exception as e:
        sys.stderr.write(f"Error executing background task: {str(e)}\n")

def main():
    current_directory = os.getcwd()
    try:
        while True:
            print_prompt()
            try:
                user_input = input().strip()
            except EOFError:
                break  # Handle EOFError to prevent crashes

            if user_input.lower() == "exit":
                break
            if not user_input:  # Ignore completely empty input
                continue

            pipe_commands = re.split(r'\s*\|\s*', user_input)
            prev_command = None
            command = None
            
            for i, command_str in enumerate(pipe_commands):
                command_str = command_str.strip()
                if not command_str:
                    continue
                
                args = command_str.split()
                if not args:
                    continue

                input_file = None
                output_file = None
                if '<' in args:
                    input_index = args.index('<')
                    input_file = args[input_index + 1]
                    del args[input_index:input_index + 2]

                if '>' in args:
                    output_index = args.index('>')
                    output_file = args[output_index + 1]
                    del args[output_index:output_index + 2]

                if args[0] == 'cd':
                    try:
                        os.chdir(args[1])
                        current_directory = os.getcwd()
                    except Exception as e:
                        print(f"cd: {str(e)}")
                elif i == 0:
                    command = find_command(args)
                    if input_file:
                        handle_input_redirection(command, input_file)
                    elif output_file:
                        handle_output_redirection(command, output_file)
                    elif command[-1] == "&":
                        execute_background_task(command[:-1])
                    else:
                        execute_command(command)
                else:
                    command = find_command(args)
                    if prev_command:
                        handle_piping(prev_command, command)
                prev_command = command
    except KeyboardInterrupt:
        print("\nShell exiting on user interrupt.")
        sys.exit(0)

if __name__ == "__main__":
    main()
