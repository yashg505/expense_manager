import yaml

def load_config_file(file_path="config.yaml"):
    """
    Loads the configuration from the specified YAML file.

    Args:
        file_path (str): Path to the YAML configuration file.

    Returns:
        dict: Parsed configuration as a dictionary.
    """
    with open(file_path, "r") as file:
        return yaml.safe_load(file)
