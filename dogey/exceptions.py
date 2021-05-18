class DogeyError(Exception):
    """ The base Dogey Exception, expect this as the main type of Dogey-specific errors such as InvalidCredentialsError. """

    pass

class DogeyCommandError(Exception):
    def __init__(self, command_name: str, message: str, *args):
        """ The basic Dogey exception for commands, expect this in on_command_error.

        Args:
            command_name (str): The name of the command.
            message (str): The message of the exception.
        """
        assert isinstance(command_name, str)
        assert isinstance(message, str)

        self.command_name = command_name
        self.message = message

        super().__init__(command_name, message, *args)

class InvalidCredentialsError(Exception):
    """An invalid token/refresh token has been passed to the Dogey client. """
    
    pass

class InstanceAlreadyCreated(DogeyError):
    """A Dogey instance has already been created, multiple calls to .start will cause this. """
    
    pass

class MissingRequiredArgument(DogeyCommandError):
    def __init__(self, command_name: str, argument: str):
        """A required argument is missing.

        Args:
            command_name (str): The command name.
            argument (str): The required argument.
        """
        assert isinstance(argument, str)

        self.command_name = command_name
        self.argument = argument

        super().__init__(command_name, f'"{argument}" is a required argument that is missing.')

class CommandNotFound(DogeyCommandError):
    def __init__(self, command_name: str):
        """A command can not be found.

        Args:
            command_name (str): The command name.
        """
        assert isinstance(command_name, str)

        self.command_name = command_name

        super().__init__(command_name, f'The command could not be found.')

class TooManyArguments(DogeyCommandError):
    def __init__(self, command_name: str):
        """Too many arguments have been passed to a command.

        Args:
            command_name (str): The command name.
        """
        assert isinstance(command_name, str)

        self.command_name = command_name

        super().__init__(command_name, f'Too many arguments have been passed.')
