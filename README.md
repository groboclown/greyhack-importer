# `greyhack-importer`

Easily import your code into the [Grey Hack](https://store.steampowered.com/app/605230/Grey_Hack/) game.

*This document uses the phrase "local computer" to refer to the computer you type into, and "game computer" to refer to the simulated computer in the Grey Hack game.*

For those jumping back to this project for reference, you probably want the [bundle JSON reference](bundle-files.md).

If you see room for improvement, please open a ticket, or, even better, submit a pull request.


## The Why

The game Grey Hack allows you to write code in a form of the [Mini Script](https://miniscript.org/) programming language, but does not give you a good way to save those on your own computer and import them into the game.

This tool aims to make importing your code into the Grey Hack game computer easy.

On top of that, this allows you to script computer setup actions and gives some quality of life improvements to get your game computer running faster.


## The What

This project introduces the concept of a Grey Hack Bundle, which is very much akin to standard programming "build" files, and very much inspired from the [`Dockerfile`](https://docs.docker.com/engine/reference/builder/) concept.

The bundles describe files, folders, and ordered operations to run.  You run from your local computer the provided script [`ghtar.py`](ghtar.py), which generates text that you can copy and paste through your computer's clipboard into the game.  Within the game, you can import, build, and run the [`import.src`](import.src) Grey Hack script to unpack the files.

The bundle files are documented in [the reference file](bundle-files.md).


## The How

1. Author your files on your local computer.  It's good to put them in one directory, but you don't need to.
2. Create a [bundle file](bundle-files.md) to describe how your local files will be put on your game computer, and how to manipulate them once they're on your game computer.
3. Run the bundle file through the `ghtar.py` program.  This generates a "grey tar" file.
4. Copy the grey tar file into your local computer's clipboard (in most text editors, you can run "ctrl-a" to select all, then "ctrl-c" to copy).
5. In the game computer, open `Notepad.exe`, paste ("ctrl-v") into notepad, and save the file to a game computer file.  Say, to `Download/import.txt`.
6. In the game computer, run the `import` tool on the grey tar file.

Before you can start to use the import tool, you need to add it to your game computer:

1. Open the [`import.src`](import.src) file on your local computer in a text editor.
2. Copy the contents of the import script to your clipboard ("ctrl-a" to select all, then "ctrl-c" to copy to the clipboard, usually works).
3. In your game computer, open `CodeEditor.exe`, paste ("ctrl-v) into the editor, and save the file to a game computer file.  Say, to `Download/import.src`.  Then build it with the play button; I put it in the home directory.

### `ghtar.py`

The [`ghtar.py`](ghtar.py) script is a Python program that does not require any libraries other than the standard Python library that comes with the language.  You'll need at least Python 3.6 to run it. *Note: this has only been tested with Python 3.11, but it should be compatible with versions down to at least 3.6.  Please open an issue if you find a problem with this.*

Depending on your operating system, you'll either run the tool as:

```bash
$ ./ghtar.py
```

or:

```bash
$ python3 ghtar.py
```

or

```bash
$ python ghtar.py
```

These instructions assume the first option, but your precise invocation syntax may be different.  You may have the file located in a different directory, in which case you need to point your invocation to its location.

The program includes friendly help messages to get you going.

When you're using reasonable sized bundles, you'll run the command with:

```
$ ./ghtar.py -o my-greytar-file.txt my-bundle.json
```

This will generate the output to a single line of very long text.  You can add the `-l` argument to break up that line into 70 column width lines, if your text editor has trouble handling long lines.

If you find your bundles are getting really big, such that the game's `Notepad.exe` gives you error messages about the file being too large to save, then you'll need to start compressing your bundle.  Use the `-z` argument to make the bundle in the compressed format.  The `import` tool works with both compressed and uncompressed, but extracting a compressed file takes longer.


### `import.src`

The `import` tool must be brought into the game (see [the instructions](#the-how) above) and built into an executable.

From there, you run the tool by opening a terminal and run it with the grey tar file as the argument:

```bash
$ import Downloads/my-cool-stuff.txt
```

The argument is either an absolute file (`/home/myself/the-file.txt`) or relative to your user's home directory, *not relative to [your working directory](https://greytracker.org/bugzilla/show_bug.cgi
?id=630).*


## The Dirty

Low level grey tar file format details:

The generated file is [Ascii85](https://en.wikipedia.org/wiki/Ascii85) encoded.  The file contains [big endian](https://en.wikipedia.org/wiki/Endianness) binary data.

The file is broken into blocks of instructions:

* byte 1: 8 bit block type identifier.
* byte 2-3: 16 bit unsigned block size.
* bytes 4-: block data.

The header block (block type 0) has 2 16-bit unsigned integers, for the file type version number and remaining header size (for future expansion).  Standard files currently use version 1, and compressed files use version 2.

Compressed files follow the header block immediately with the dictionary reference, then the encoded body.  They do not have blocks, but instead, after the body is decoded, it is parsed as a complete binary, block-format file.

The compression header contains a series of value lookup blocks.  A lookup block contains 1 byte with the top 4 bits set to the number of bytes in each lookup's mapped value minus 1 (that is, if the lookup contains the value "abc", then the lookup length will be 2), and the lower 4 bits set to the number of items in the block.  If the number of items is 0, then this is an end-of-block marker.  The order of the lookup items relates to its encoded index (the first lookup item is index 0, the second 1, and so on).

The encoded body contains a series of 12-bit lookup values (big endian), with lookup value 4095 reserved for an "end of stream" marker.  The decoder reads the 12 bits, uses that as the index in the lookup blocks, and inserts the lookup block data into the resulting decoded stream.


# Developing

The `ghtar.py` file is transformed via Black for a consistent style.  It is also run through MyPy to check for type errors.


# Version History

* 3.1.0 - Added file encoding for storing binary files on the game computer.  Fixed a bug with encoding uncompressed files.
* 3.0.0 - Backwards incompatible change for the handling of 'test' blocks, added to fix a bug with shared files during testing.
* 2.1.0 - Bug fix with loading files.
* 2.0.0 - Supported compressed files.
* 1.0.0 - Initial development.

# License

Released under the [MIT License](LICENSE).
