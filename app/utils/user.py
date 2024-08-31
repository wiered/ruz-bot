fgdghfd = {
    "id": {
        "group_id": "group_id",
        "group_name": "group_name"
    }
}

class Users():
    """
    Class for managing users in the bot.
    
    Attributes:
        users_dict (dict): A dictionary with user's id as key and a dictionary
            with group_id and group_name as values.
    """
    def __init__(self):
        """
        Initializes the Users object.
        """
        self.users_dict = {}
        
    def addUser(self, _id, group_id, group_name):
        """
        Adds a new user to the users_dict dictionary.
        
        Args:
            _id (int): The user's id.
            group_id (int): The user's group id.
            group_name (str): The user's group name.
        """
        self.users_dict.update({
            _id: {
                "group_id": group_id,
                "group_name": group_name
            }
        })
        
    def updateUser(self, _id, group_id, group_name):
        """
        Updates the user's data in the users_dict dictionary.
        
        Args:
            _id (int): The user's id.
            group_id (int): The user's group id.
            group_name (str): The user's group name.
        """
        self.users_dict.update({
            _id: {
                "group_id": group_id,
                "group_name": group_name
            }
        })
            
    def getUser(self, _id):
        """
        Returns the user's data from the users_dict dictionary.
        
        Args:
            _id (int): The user's id.
        
        Returns:
            dict: The user's data if found, otherwise None.
        """
        return self.users_dict.get(_id)
            
    def getAllUsers(self) -> dict:
        """
        Returns the entire dictionary of all users in the form of {user_id: {group_id, group_name}}.
        
        Returns:
            dict: The entire dictionary of all users.
        """
        return self.users_dict
    
    def setDB(self, db: dict) -> None:
        """
        Sets the dictionary of all users in the form of {user_id: {group_id, group_name}}.
        
        Args:
            db (dict): The entire dictionary of all users.
        """
        self.users_dict = db

    
    def isUserKnown(self, _id) -> bool:
        """
        Checks if the user is in the users_dict dictionary.
        
        Args:
            _id (int): The user's id.
        
        Returns:
            bool: True if the user is in the dictionary, False otherwise.
        """
        # Check if the user is in the dictionary
        if self.users_dict.get(_id):
            # If the user is in the dictionary, return True
            return True
        
        # If the user is not in the dictionary, return False
        return False
    
    def getUsersJson(self) -> list:
        """
        Converts the users_dict dictionary into a JSON serializable list of dictionaries.
        
        Returns:
            list: A list of dictionaries in the form of {user_id: {group_id, group_name}}.
        """
        users_json = []
        for user in self.users_dict.keys():
            # Get the user's data from the users_dict dictionary
            user_data = self.users_dict.get(user)
            # Create a new dictionary with the user's data
            user_json = {
                "id": user,  # The user's id
                "group_id": user_data.get("group_id"),  # The user's group id
                "group_name": user_data.get("group_name")  # The user's group name
            }
            # Add the user's data to the list of JSON serializable dictionaries
            users_json.append(user_json)
            
        # Return the list of JSON serializable dictionaries
        return users_json

    