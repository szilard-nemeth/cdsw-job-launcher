#!/usr/bin/env python3
import os
import sys

from cdswjoblauncher.cdsw.cdsw_runner import ArgParser

# THESE FUNCTION DEFINITIONS AND CALL TO fix_pythonpast MUST PRECEDE THE IMPORT OF libreloader: from libreloader import reload_dependencies
# TODO same as CdswEnvVar.PYTHONPATH --> Migrate
PYTHONPATH_ENV_VAR = "PYTHONPATH"


def get_pythonpath():
    return os.environ[PYTHONPATH_ENV_VAR]


def set_env_value(env, value):
    os.environ[env] = value


def add_to_pythonpath(additional_dir):
    pypath = PYTHONPATH_ENV_VAR
    if pypath in os.environ:
        print(f"Old {pypath}: {get_pythonpath()}")
        set_env_value(pypath, f"{get_pythonpath()}:{additional_dir}")
        print(f"New {pypath}: {get_pythonpath()}")
    else:
        print(f"Old {pypath}: not set")
        set_env_value(pypath, additional_dir)
        print(f"New {pypath}: {get_pythonpath()}")
    sys.path.append(additional_dir)
    print("Fixed sys.path: " + str(sys.path))
    print("Fixed PYTHONPATH: " + str(os.environ[pypath]))



def main():
    if len(sys.argv) != 3:
        # TODO NEW
        raise ValueError("Unexpected number of arguments. "
                         "Should call the script with these arguments: start_job.py <module-name> <job-name> <default-email-recipients")
    module_name = sys.argv[1]
    job_name = sys.argv[2]
    default_mail_recipients = sys.argv[3]

    # Only used script is the libreloader from /home/cdsw/scripts/
    cdsw_home_dir = os.path.join("/home", "cdsw")
    scripts_dir = os.path.join(cdsw_home_dir, "scripts")
    jobs_dir = os.path.join(cdsw_home_dir, "jobs")
    add_to_pythonpath(scripts_dir)

    # NOW IT'S SAFE TO IMPORT LIBRELOADER
    # IGNORE FLAKE8: E402 module level import not at top of file
    from libreloader import reload_dependencies  # DO NOT REMOVE !! # noqa: E402
    from libreloader.reload_dependencies import Reloader  # DO NOT REMOVE !! # noqa: E402

    print(f"Name of the script      : {sys.argv[0]=}")
    print(f"Arguments of the script : {sys.argv[1:]=}")
    if len(sys.argv) != 2:
        raise ValueError("Should only have one argument, the name of the job!")

    reload_dependencies.Reloader.start(module_name)



    # Get the Python module root
    module_root = reload_dependencies.Reloader.get_python_module_root()
    yarn_dev_tools_module_root = os.path.join(module_root, module_name)
    # TODO NEW this path is invalid
    cdsw_runner_path = os.path.join(yarn_dev_tools_module_root, "cdsw", "cdsw_runner.py")
    print("YARN dev tools module root is: %s", Reloader.MODULE_ROOT)

    # Start the CDSW runner
    sys.argv.append("--config-dir")
    sys.argv.append(jobs_dir)
    sys.argv.append("--default-email-recipients")
    sys.argv.append(default_mail_recipients)
    exec(open(cdsw_runner_path).read())


if __name__ == '__main__':
    main()
