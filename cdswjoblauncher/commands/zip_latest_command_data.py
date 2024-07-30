import logging
from typing import List

from pythoncommons.file_utils import FileUtils
from pythoncommons.zip_utils import ZipFileUtils

from cdswjoblauncher.commands.cmd_type import LATEST_DATA_ZIP_LINK_NAME

LOG = logging.getLogger(__name__)


class CommandDataZipperConfig:
    def __init__(self,
                 dest_dir,
                 ignore_filetypes: List[str],
                 input_files: List[str],
                 project_basedir,
                 cmd_type_real_name: str,
                 dest_filename: str = None):
        self.cmd_type_real_name = cmd_type_real_name
        self.input_files = input_files
        self.output_dir = dest_dir
        self.project_out_root = project_basedir
        self.ignore_filetypes = ignore_filetypes
        self.dest_filename = self._get_dest_filename(dest_filename, cmd_type_real_name)

    @staticmethod
    def _get_dest_filename(dest_filename, cmd_type_real_name: str):
        fname = dest_filename
        if fname:
            LOG.info(f"Using overridden destination filename: {fname}")
        else:
            fname = f"command_data_{cmd_type_real_name}.zip"
        return fname


class ZipLatestCommandData:
    def __init__(self, config: CommandDataZipperConfig):
        self.config = config
        self._check_input_files(config.input_files, config.project_out_root)

    @property
    def cmd_type(self):
        return self.config.cmd_type_real_name

    def _check_input_files(self, input_files: List[str], basedir: str):
        LOG.info(f"Checking provided input files. Command: {self.cmd_type}, Files: {input_files}")

        resolved_files = []
        for fname in input_files:
            if "*" in fname:
                fname = fname.replace("*", ".*")
                found_files = FileUtils.find_files(
                    basedir, regex=fname, single_level=True, full_path_result=True
                )
                LOG.info("Found files for pattern '%s': %s", fname, found_files)
                resolved_files.extend(found_files)
            else:
                resolved_files.append(FileUtils.join_path(basedir, fname))

        # Sanity check
        not_found_files = []
        for f in resolved_files:
            exists = FileUtils.does_file_exist(f)
            if not exists:
                not_found_files.append(f)
        if len(not_found_files) > 0:
            raise ValueError(f"The following files could not be found: {not_found_files}")

        LOG.info(f"Listing resolved input files. Command: {self.cmd_type}, Files: {resolved_files}")
        return resolved_files

    def run(self):
        LOG.info(
            "Starting zipping latest command data... \n "
            f"PLEASE NOTE THAT ACTUAL OUTPUT DIR AND DESTINATION FILES CAN CHANGE, IF NOT SPECIFIED\n"
            f"Output dir: {self.config.output_dir}\n"
            f"Input files: {self.config.input_files}\n "
            f"Destination filename: {self.config.dest_filename}\n "
            f"Ignore file types: {self.config.ignore_filetypes}\n "
        )

        zip_file_name, temp_dir_dest = ZipFileUtils.create_zip_file_advanced(
            self.config.input_files, self.config.dest_filename, self.config.ignore_filetypes, self.config.output_dir
        )
        FileUtils.create_symlink_path_dir(LATEST_DATA_ZIP_LINK_NAME, zip_file_name, self.config.project_out_root)

        # Create the latest link for the command as well
        # TODO cdsw-separation This is copied from CommandType.command_data_zip_name --> Better way to specify?
        FileUtils.create_symlink_path_dir(
            f"{LATEST_DATA_ZIP_LINK_NAME}-{self.cmd_type}", zip_file_name, self.config.project_out_root
        )

        # Save command data file per command to home dir when temp dir mode is being used
        if temp_dir_dest:
            # TODO cdsw-separation This is copied from CommandType.command_data_name --> Better way to specify?
            zip_file_name_real: str = f"latest-command-data-{self.cmd_type}-real.zip"
            target_file_path = FileUtils.join_path(self.config.project_out_root, FileUtils.basename(zip_file_name_real))
            FileUtils.copy_file(zip_file_name, target_file_path)
