class DogeyError(Exception):
    """The base Dogey Exception class, expect this as the main type of Dogey-specific errors. """
    def __init__(self, message: str, *args):
        """
        Args:
            msg (str): The message of the Exception
        """
        self.message = message
        super().__init__(message, *args)
    pass

class InvalidCredentialsError(DogeyError):
    """An invalid token/refresh token has been passed to the Dogey client. """
    
    pass

class InstanceAlreadyCreated(DogeyError):
    """For when the Dogey instance has already been created, multiple calls to .start will cause this. """
    
    pass

class MissingRequiredArgument(DogeyError):
    def __init__(self, argument: str):
        """A required argument is missing.

        Args:
            argument (str): The required argument
        """
        assert isinstance(argument, str)

        self.argument = argument
        super().__init__(f'"{argument}" is a required argument that is missing.')

class CommandNotFound(DogeyError):
    """ For when a command can not be found. """

    def __init__(self, command_name: str):
        """A command can not be found

        Args:
            command_name (str): [description]
        """
        assert isinstance(command_name, str)

        self.command_name = command_name
        super().__init__(f'The command "{command_name}" can\'t be found.')
