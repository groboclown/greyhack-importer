"""Stand alone script to print some basic information."""

import greyhack

greyhack.clear_screen()

print("User home dir: " + greyhack.home_dir())
print("Program path: " + greyhack.program_path())
print("Bank number: " + greyhack.user_bank_number())
print("Mail address: " + greyhack.user_mail_address())

if greyhack.home_dir() == greyhack.parent_path(greyhack.program_path()):
    print("This script exists in the home directory.")
