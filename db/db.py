import csv
import logging

def load_from_csv(file_name):
    """
    Loads users from a CSV file into a list of dictionaries.

    The CSV file is expected to have the following columns:

    - id: The user's ID in Telegram
    - group_id: The user's group ID
    - group_name: The user's group name

    :param file_name: The name of the CSV file to load
    :return: A list of dictionaries, each containing a user's data
    """
    # show current path of an app
    import os
    print(os.getcwd())
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except FileNotFoundError:
        logging.error('File not found')
        # Run echo command to create empy file
        open(file_name, 'w').close()
        logging.info('File created')
        load_from_csv(file_name)

def write_to_csv(file_name, data):
    """
    Saves a list of dictionaries to a CSV file.

    The CSV file is expected to have the following columns:

    - id: The user's ID in Telegram
    - group_id: The user's group ID
    - group_name: The user's group name

    :param file_name: The name of the CSV file to save
    :param data: A list of dictionaries, each containing a user's data
    """
    # Clear the file before writing
    open(file_name, 'w').close()
    with open(file_name, 'w', encoding='utf-8') as f:
        # Create a CSV writer with the expected columns
        writer = csv.DictWriter(
            f, 
            fieldnames=[
                'id', 
                'group_id',
                'group_name'
            ]
            )
        # Write the header
        writer.writeheader()
        # Write the data
        writer.writerows(data)
        # Log that the data has been saved
        logging.info('Users saved')
