#!/usr/bin/env python3
import os
import sys

# THESE FUNCTION DEFINITIONS AND CALL TO fix_pythonpast MUST PRECEDE THE IMPORT OF libreloader: from libreloader import reload_dependencies
# TODO same as CdswEnvVar.PYTHONPATH --> Migrate
PPATH = "PYTHONPATH"

# TODO cdsw-separation Eliminate this file completely

def add_to_pythonpath(additional_dir):
    if PPATH in os.environ:
        print(f"Old {PPATH}: {os.environ[PPATH]}")
        os.environ[PPATH] = f"{os.environ[PPATH]}:{additional_dir}"
        print(f"New {PPATH}: {os.environ[PPATH]}")
    else:
        print(f"Old {PPATH}: not set")
        os.environ[PPATH] = additional_dir
        print(f"New {PPATH}: {os.environ[PPATH]}")
    sys.path.append(additional_dir)
    print("Fixed sys.path: " + str(sys.path))
    print("Fixed PYTHONPATH: " + str(os.environ[PPATH]))



def main():
    print(f"Name of the script      : {sys.argv[0]=}")
    print(f"Arguments of the script : {sys.argv[1:]=}")

    if len(sys.argv) != 3:
        # TODO cdsw-separation
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

    reload_dependencies.Reloader.start(module_name)

    # Get the Python module root
    python_site = reload_dependencies.Reloader.get_python_module_root()
    module_root = os.path.join(python_site, module_name)
    # TODO cdsw-separation this path is invalid
    cdsw_runner_path = os.path.join(module_root, "cdsw", "cdsw_runner.py")
    print("Module root is: %s", Reloader.MODULE_ROOT)

    # Start the CDSW runner
    sys.argv.append("--config-dir")
    sys.argv.append(jobs_dir)
    sys.argv.append("--default-email-recipients")
    sys.argv.append(default_mail_recipients)
    exec(open(cdsw_runner_path).read())


if __name__ == '__main__':
    main()
