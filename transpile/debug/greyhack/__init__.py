"""Type annotation of the GreyHack API."""

import typing


ImportedLibType = typing.TypeVar("ImportedLibType")


class CTFEvent:
    """Capture the flag event."""


class Router:
    """Router information."""


class Shell:
    """Shell information."""


class Switch:
    """Switch information."""


class MetaMail:
    """E-Mail information."""


def active_user() -> str:
    """Returns a string with the name of the user who is executing the script."""


BitwiseOperator = typing.Literal["&", "|", "^", "<<", ">>", ">>>"]


def bitwise(operator: BitwiseOperator, num1: int, num2: int) -> int:
    """Bitwise operators are used for manipulating data at the bit level.

    Bitwise operates on one or more bit patterns or binary numerals at the
    level of their individual bits.  They are used in numerical computations to make
    the calculation process faster."""


def clear_screen() -> None:
    """Delete any text from the terminal."""


def command_info(key_command: str) -> str:
    """Returns the information of common commands of the Operating System, such as mkdir, whois, etc."""


def current_date() -> str:
    """Returns the time and date."""


def current_path() -> str:
    """It returns a string with the path in which the terminal is at the moment of launching the script."""


def exit(*, message: str = None) -> None:
    """Stops the execution of the script at the time this method is executed.

    Optionally you can pass a string as a message that will be printed in the
    terminal when the program ends.
    """


def format_columns(text: str) -> None:
    """Format the text provided so that it is ordered by columns."""


def get_ctf(user: str, password: str, event_name: str) -> CTFEvent | str:
    """Gets the created event from create_ctf.

    In case of success, it will return a CTFEvent type object, otherwise it will
    return a string with the error.
    """


def get_custom_object() -> dict[str, typing.Any]:
    """Returns an empty Map object that can be used to share data back and
    forth with programs launched with shell.launch
    """


def get_router(ip_address: str | None = None) -> Router | None:
    """Returns the router whose public IP matches, otherwise returns null.

    If the ip_address parameter is not specified, returns the router to which the
    computer executing this command is connected.
    """


def get_shell(user: str | None = None, password: str | None = None) -> Shell | None:
    """Returns the shell that is executing the script if it is called without parameters.

    Passing a username and password, it returns a shell with those credentials if are correct.
    """


def get_switch(ip_address: str | None = None) -> Switch | None:
    """Returns the switch on the local network whose IP matches, otherwise it returns null."""


def home_dir() -> str:
    """Returns a string with home folder path of the user who is executing the script."""


# Not listed: import_code


def include_lib(
    lib_path: str, type: typing.Type[ImportedLibType]
) -> ImportedLibType | None:
    """Includes an external library to be used in scripting.

    If the library has been included correctly, it will return an object
    of corresponding type with the library, null otherwise.

    Extended here for Python typing to take a type description.
    """


def is_lan_ip(ip_address: str) -> bool:
    """Returns true if the provided address is local, false otherwise. If the provided IP is not valid, it also returns false."""


def is_valid_ip(ip_address: str) -> bool:
    """Returns true if the provided address is valid, false otherwise."""


def launch_path() -> str:
    """Returns the location of the launched script (?)."""


def mail_login(user: str, password: str) -> MetaMail | str:
    """Access the email account and returns a MetaMail type object if the login has been correct.

    In case of error, it returns a string.
    """


def nslookup(web_address: str) -> str:
    """Returns the IP address that is behind the web address that has been provided."""


def parent_path(path: str) -> str:
    """Returns the path provided without the last element.

    It does not take into account if the path exists."""


def print(message: str) -> None:
    """Print on the Terminal the message."""


def program_path() -> str:
    """Returns a string with the path of the program that is running at this time."""


def reset_ctf_password(new_password: str) -> None:
    """Change the password of the CTF account.

    Only the account owner can change the password. Returns true if the process
    completed successfully, in case of error a string with the details is returned.
    """


def typeof(obj: typing.Any) -> str:
    """Returns a string with the type of the object passed as a parameter."""


def user_bank_number() -> str:
    """Returns a string with the bank account number of the user who is executing this script."""


def user_input(
    prompt_msg: str = "", password_mode: bool = False, any_key: bool = False
) -> str:
    """It puts the program on hold to receive the user input, which will be processed as a string.

    If the password mode is activated, the input text will be hidden with asterisks.

    If the anyKey argument is true, the entered character will be captured without pressing enter.
    """


def user_mail_address() -> str:
    """Returns a string with the user's email address that is executing this script."""


def wait(seconds: float = 1.0) -> None:
    """Pauses the script for the indicated time.

    If duration is not specified, the default value is 1 second.
    """


def whois(ip_address: str) -> str:
    """Shows the administrator information behind the IP provided."""
