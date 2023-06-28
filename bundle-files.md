# Bundle File Format

A bundle file is a JSON formatted file that's an array (the contents are surrounded by '[' and ']' characters).  Each element in this is a "block" instruction that is a map, which includes the `"type"` key to describe the kind of operation that block performs.

When the tool runs to process the instructions, it runs under the user that you run the command.  So, it will only be able to perform the operations your user has permissions to run.

The import script will create folders first, then add files that are bundled, then finally run the operations in the order they were given.

Supported block types are:

## type: `about`

**Keys:**

* `type`: `about`
* `bundle-version`: (optional) string containing the version of the bundle file that this is written for.  This should be set to "2" if you set it.
* `version`: (optional) string containing the bundle's version.

This is a meta-data, informational block, intended to add additional context around the purpose of the bundle.

## type: `folder`

**Keys:**

* `type`: `folder`
* `path`: the folder path to create in the game's computer.

**Example:**

```json
[
    {
        "type": "folder",
        "path": "/home/myuser/bin/trials"
    }
]
```

This will create the folder `/home/myuser/bin/trials` in the game.  If the directories leading up to that path do not exist, they will be created.

This example could have used the format `~/bin/trials` as a short-hand to indicate that the directory `bin/trials` should be created within the running user's home directory.

## type: `file`

**Keys:**

* `type`: `file`
* `path`: the destination of the file in the game's computer
* `contents`: the text in this key will be the contents of the file, if given.
* `local`: path to a file on your local computer, relative to the bundle file's location, containing text that will be added to the game's file.

You must provide exactly one of the `contents` key or the `local` keys.

If the path includes a folder that doesn't exist, or that isn't given in a [`folder`](#type-folder) block, then the folders leading to the file will be created.

**Example:**

```json
[
    {
        "type": "file",
        "path": "/home/myuser/notes.txt",
        "local": "game-notes.txt"
    }
]
```

Adds the contents in the file `game-notes.txt`, which must be located in the same directory as the bundle file, into the game under the path `/home/myuser/notes.txt`

This example could have used the format `~/notes.txt` as a short-hand to indicate that the file `notes.txt` should be created within the running user's home directory.

## type: `source`

**Keys:**

* `type`: `source`
* `path`: the destination of the file in the game's computer
* `local`: path to a file on your local computer, relative to the bundle file's location, containing text that will be added to the game's file.

This is very similar to the [file](#type-file) block, but has special handling for Grey Script source files.

* The files will be slimmed down to remove comments and extra whitespace.  This helps get past limitations on file sizes.  Note that newlines aren't changed, so errors caused by running the script should still report the same line number, to allow for easier debugging.
* If the text `<[HOME]>` occurs anywhere in the file, it is replaced with the home directory for the user that runs the import script.
* The biggest change is special handling for `import_code()` instructions.

    Because the Grey Hack game only parses exact, fully qualified file names, and doesn't allow relative imports or syntax like `home_dir + "/file"`, text included in the `source` block handles these lines very carefully, under strict rules.  The instruction `import_code()` must be on its own line, and must have a quoted string within the parenthesis.

    If those criteria are met, then the file within the quoted text is assumed to reference another file on your local computer relative to the location of the source file.  That referenced file will be brought into the bundle, and the source file will be modified to reference the new location of the imported file.

    Because of additional limitations on file names, the imported file names will be modified to make them allowable for import.

**Example:**

```json
[
    {
        "type": "source",
        "path": "~/funtimes.src",
        "local": "fun-times.gs"
    }
]
```

## type: `build`

**Keys:**

* `type`: `build`
* `source`: the location of the source file to build in the game's computer.
* `target`: the location of the compiled output file in the game's computer.

This performs the `build` command to compile the `source` file to the `target` file.  Unlike the terminal's build command, this will rename the output file to be exactly the target filename.

This command does not add files to the bundle; it just runs an instruction on files on the computer.  The command will always run after embedded files and folders are extracted from the bundle.


## type: `test`

**Keys:**

* `type`: `test`
* `local`: path to a file on your local computer, relative to the bundle file's location, containing text that will be added to the game's file.  This can be either one file (a string) or a list of files (array of strings).  The files can also include glob patterns (like `*.src`).

When the tool unpacks a test block, each of the files specified is saved to a temporary file are created in the game computer, compiled with the `build` command, and run.  The file is added under the same rules as the `source` included files, so `import_code()` will include those files in the bundle, and the references will be updated to point to their location.


## type: `compile`

**Keys:**

* `type`: `compile`
* `local`: (string) path to a file on your local computer, relative to the bundle file's location, containing the program code to compile.
* `local-tests`: (optional list of strings or string) path to files on your local computer, relative to the bundle file's location, that run code before compiling the `local` file.
* `target`: (string) the location of the compiled output file in the game's computer.

Bundles the `local` file using the [`source`](#type-source) rules.  The file is saved in a temporary file in the game's computer, then built using the `build` tool, and put into the `target` path in the game's computer.


## type: `user`

**Keys:**

* `type`: `user`
* `user`: name of the user to create
* `password` password to assign the newly created user

Add the given user to the game's computer, and assign it the given password.  This will only succeed if the user running the import operation has permissions to add a user.


## type: `group`

**Keys:**

* `type`: `group`
* `group`: name of the group to add to the user; it will be created if it doesn't exist.
* `user`: user name to add to the group

Adds the group to the given user in the game's computer.  This will only succeed if the user running the import operation has permissions to create a group or add a group to a user.


## type: `rm-user`

*Since v3.0.0*

**Keys:**

* `type`: `rm-user`
* `user`: name of the user to create
* `rm-home` (optional) `true` if the home directory should also be removed; defaults to `false`.

Remove the given user to the game's computer, and optionally removes the user home directory.  This will only succeed if the user running the import operation has permissions to add a user.


## type: `rm-group`

*Since v3.0.0*

**Keys:**

* `type`: `rm-group`
* `group`: name of the group to add to the user; it will be created if it doesn't exist.
* `user`: user name to add to the group

Removes the group from the given user in the game's computer.  This will only succeed if the user running the import operation has permissions to remove a group from a user.


## type: `chmod`

**Keys:**

* `type`: `chmod`
* `path`: location of the file or folder on the game's computer
* `permissions`: chmod permission string to use.  For example, `u+wx`.
* `recursive`: (optional) `true` or `false` to indicate whether, if the path is a folder, to perform the permission change to all files in the path.  This value defaults to `false`.

Changes permissions on the path.  If `recursive` is given and is `true` and the `path` references a folder, then the folder along with the contents of the folder will have the same permissions assigned.

This will only succeed if the user running the import operation has permissions to modify the file.

## type: `chown`

**Keys:**

* `type`: `chown`
* `path`: location of the file or folder on the game's computer
* `owner`: can be in the format `username:groupname` to assign both user and group ownership to the path.  If no `:` is in the text, then just the username is assigned.
* `user`: the exact username to assign ownership to the path.
* `recursive`: (optional) `true` or `false` to indicate whether, if the path is a folder, to perform the ownership change to all files in the path.  This value defaults to `false`.

Changes the owner of the path.  If `recursive` is given and is `true` and the `path` references a folder, then the folder along with the contents of the folder will have the same ownership assigned.

Exactly one of `owner` or `user` must be given.  If `owner` is given in the form `username:groupname`, then this is a short-hand for running `chown` and [`chgroup`](#type-chgroup) on the path.

This will only succeed if the user running the import operation has permissions to modify the file.


## type: `chgroup`

**Keys:**

* `type`: `chown`
* `path`: location of the file or folder on the game's computer
* `group`: the exact group name to assign ownership to the path.
* `recursive`: (optional) `true` or `false` to indicate whether, if the path is a folder, to perform the ownership change to all files in the path.  This value defaults to `false`.

Changes the group owner of the path.  If `recursive` is given and is `true` and the `path` references a folder, then the folder along with the contents of the folder will have the same ownership assigned.

This will only succeed if the user running the import operation has permissions to modify the file.


## type: `exec`

**Keys:**

* `type`: `exec` or `run`
* `cmd`: location of the file on the game's computer to execute.
* `arguments`: (optional) either a string with the command arguments, or an array of arguments, to pass to the command.

Runs the command with the given arguments.


## type: `copy`

**Keys:**

* `type`: `copy` or `cp`
* `from`: the source file or folder location on the game's computer to copy.
* `to`: the target file or folder location on the game's computer.  This will be the exact name of the copy.

Copies a file or folder from one location to anther location.

**Example:**

```json
[
    { "type": "file", "contents": "hello", "path": "/home/myuser/Downloads/h.txt" },
    { "type": "copy", "from": "/home/myuser/Downloads", "to": "/home/myuser/Backup" }
]
```

This will create the file `/home/myuser/Downloads/h.txt` containing the text `hello`.  Then, it will copy the entire contents of the `/home/myuser/Downloads` folder to a new folder named `/home/myuser/Backup`.  When the operation completes. there will exist a file named `/home/myuser/Backup/h.txt` containing the text `hello`.


## type: `move`

**Keys:**

* `type`: `move`, `mv`, `rename`, or `ren`
* `from`: the source file location on the game's computer to move.
* `to`: the target file location on the game's computer.

Moves a file or folder from one location to anther location.


## type: `delete`

**Keys:**

* `type`: `delete`, `del`, or `rm`
* `path`: the file or empty folder location on the game's computer to delete.

Deletes the file or folder from the game's computer.  If deleting a folder, then the folder must be empty.


## type: `bundle`

**Keys:**

* `type`: `bundle`
* `local`: path to the local bundle file.

Adds the contents of another bundle file into this assembled bundle.  If one bundle references another, it also will be included.  Duplicates will be ignored.
