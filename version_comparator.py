import subprocess
import yaml
import os
import tempfile
import logging
from io import BytesIO

def run_external_comparison(config_dict, progress_callback=None):
    """
    Generates a config.yml file in a temporary directory, runs the 
    external 'sparql-diff' command against it, and returns the resulting 
    Excel file as a BytesIO object for in-memory handling.
    """
    # Use a temporary directory to avoid cluttering the project folder.
    # The directory and its contents are automatically deleted upon exit.
    with tempfile.TemporaryDirectory() as temp_dir:
        config_filename = 'config.yml'
        config_path = os.path.join(temp_dir, config_filename)
        output_filename = 'changelog_output.xlsx'
        output_path = os.path.join(temp_dir, output_filename)

        # The external tool needs the output_path inside the config file.
        config_dict['output_path'] = output_path
        
        # Write the dynamically generated config to the temp file
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)

        # Define the command to be executed.
        # 'sparql-diff' is the entry point defined in the library's setup.
        command = ['sparql-diff']

        try:
            if progress_callback:
                progress_callback(0.5, "Executing external comparison tool...")
            
            # The 'sparql-diff' tool expects 'config.yml' to be in the
            # directory from which it is run. We use `cwd` to achieve this.
            process = subprocess.run(
                command,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                check=True  # Raise an exception for non-zero exit codes
            )
            
            # Log the output for debugging purposes
            logging.info("sparql-diff stdout:\n" + process.stdout)
            if process.stderr:
                logging.warning("sparql-diff stderr:\n" + process.stderr)

            if progress_callback:
                progress_callback(0.9, "Reading generated report...")

            # After the tool runs, read the generated Excel file into memory
            if os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    excel_data = BytesIO(f.read())
                return excel_data
            else:
                # This case handles if the tool succeeds but doesn't create the file
                raise FileNotFoundError(
                    "The comparison tool ran successfully but did not create the expected output file.\n"
                    f"Tool output:\n{process.stdout}\n{process.stderr}"
                )

        except subprocess.CalledProcessError as e:
            # This catches errors if the tool itself fails (e.g., non-zero exit code)
            error_message = (
                f"The external comparison tool failed with exit code {e.returncode}.\n\n"
                f"--- STDOUT ---\n{e.stdout}\n\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            logging.error(error_message)
            raise RuntimeError(error_message) from e
        
        except FileNotFoundError:
            # This catches the error if the 'sparql-diff' command isn't found
            raise RuntimeError(
                "The 'sparql-diff' command was not found. Please ensure the "
                "RDF-PythonSnippets library is installed correctly in your environment "
                "and that its scripts are available in your system's PATH."
            )

