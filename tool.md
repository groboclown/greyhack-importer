# greyscript

Grey Hack Scripts and tools for working with the Grey Hack game.

# Provided Tools

## MC Shell

Read [the docs](mc.md).

## Import Files into the Game

The Grey Hack game provides an in-game editor, but it has severe limitations.  Additionally, the game makes it very difficult to develop text files on your local computer outside the game, then import them into the game.

This project introduces the concept of a Grey Hack Bundle, which is very much akin to standard programming "build" files, and very much inspired from Dockerfiles.

The bundles describe files, folders, and ordered operations to run.  You run from your local computer the provided script [`ghtar.py`](bin/ghtar.py), which generates text that you can copy and paste through your computer's clipboard into the game.  Within the game, you can import, build, and run the [`make.src`](src/make.src) Grey Hack script to unpack the files.

### Bundle Files

The `ghtar.py` tool processes "bundle" files that describe how to assemble your local files and process them within the game.  Example bundle files are in the [bundles](bundles/) directory.

A bundle file is a JSON formatted file that's an array (the contents are surrounded by '[' and ']' characters).  Each element in this is a "block" instruction that is a map, which includes the `"type"` key to describe the kind of operation that block performs.

The file format and supported block types is described in the [bundle file](bundle-files.md) document.

### Setting Up the bundle `make` tool

To process the bundle file in the Grey Hack game, you'll need to import the [make.src](src/make.src) program and build it.

1. In the Grey Hack game, launch the CodeEditor.
2. On your local computer, open the file [src/make.src](src/make.src) in a text editor or browser, and copy the raw contents into your computer's clipboard (ctrl-c usually does the trick).
3. In the Grey Hack game, paste into the CodeEditor (ctrl-v usually does the trick).
4. In the CodeEditor, save the file to `Downloads/make.src`, then build it to `make` (you can change the paths as you please).  You can then close the CodeEditor if you want.


### Running `ghtar`

You'll need [Python 3](https://www.python.org/) installed, at least version 3.6 (it's tested with 3.11, so please report bugs if you encounter compatibility issues).

```bash
$ python bin/ghtar.py --help
```

will present you with the full help documentation.

In general, if you have a bundle file `my-bundle.json`, you'll want to put the generated gh-tar file into a text file:

```bash
$ python bin/ghtar.py -o import.txt my-bundle.json
```

If the files are bigger than about 100k, the game will tell you that the file is too big.  You'll need to either slim down your bundle, or try running with the compress (`-z`) option.

From there, you want to import the text into your game's computer.  You will first need to [set up `make` in your game's computer](#setting-up-the-bundle-make-tool).

1. In the Grey Hack game, open Notepad.
2. On your local computer, open the output bundle file in a text editor or browser (in the example above, it was named `import.txt`), and copy the raw contents into your computer's clipboard.
3. Save the file to `Downloads/import.txt` (you can change the path if you please).
4. Open a terminal window, and type `make Downloads/import.txt`
    * Note: `make` processes the first argument as a file.  If it can't find it as an absolute file, then it tries looking for the file relative to your user's home directory.  It would be nice if it could look relative to your current working directory, but [there's an old bug on this](https://greytracker.org/bugzilla/show_bug.cgi?id=630).

The generated text is an [Ascii85](https://en.wikipedia.org/wiki/Ascii85) encoded binary file, which is broken into small chunks for an optimally sized file.  When compressed, it is a custom dictionary lookup compression scheme and can obtain around 50% reduction in size for normal text files.


## Game File Layout

This repository expects the files in the game to be laid out just like the repository.


## Coding Standard

In general, a Go coding standard is used for comments and naming.

### Classes

Classes use functions named "New*" to create new instances, and "init" as initializers.  For an example, see the [extract.gs](programs/extract.gs) program.

If a class provides a string representation, it should do so in the ".Text" value or function.

### Errors

Functions that can generate an error return a list: [error, result].  The "error" is `null` if there is no error, otherwise it's something that should be displayable to the end user.


### Library: Context

(Still needs to be documented.  The rough sketch of the library and its use is in the monitor program.)


# Developing The Python Scripts

The Python scripts are intended to be stand-alone and not require external packages to run.

To develop them, they must pass a `mypy` run and be processed through `black`:

```bash
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install --upgrade -r build-requirements.txt
$ black bin/*.py
$ mypy bin/*.py
```


# Notes:

`print()` command has formatting that's supported a bit by [this](http://digitalnativestudios.com/textmeshpro/docs/rich-text/)

Supported character codes in the fonts:

// 161 - upsidedown !
// 162 - cent sign
// 163 - pound sign
// 164 - currency sign
// 165 - yen
// 166 - broken vertical pipe
// 167 - sign
// 168 - umlaut
// 169 - copyright
// 170 - superscript a
// 171 - <<
// 172 - logical not
// 174 - restricted TM
// 175 - high bar / long mark
// 176 - circle diadectic
// 177 - +/-
// 178 - squared
// 179 - cubed
// 180 - back tick diadectic
// 181 - mu
// 182 - paragraph
// 183 - center dot
// 184 - cillia
// 185 - superscript 1
// 186 - degree
// 187 - >>
// 188 - 1/4
// 189 - 1/2
// 190 - 3/4
// 191 - upsidedown ?
// 192-255 - accented characters
// 247 - division
// 215 - multiplication
// 286-287 - accent g
// 304 - I accent
// 305 - digamma
// 350-351 - S accent.
// 1024-1279 - cyralic
// 1154 - kind of unequal
// 3585-3675 - arabic?
// 8208,8210-8213 - -
// 8214 - ||
// 8215 - low _
// 8216 - nice left single quote
// 8217 - nice right single quote
// 8218 - nice comma
// 8219 - upside down nice left single quote
// 8220 - nice left double quote
// 8221 - nice right double quote
// 8222 - nice left double quote, bottom
// 8224 - cross
// 8225 - double cross
// 8226 - big dot
// 8230 - elipses
// 8240 - basis points
// 8242 - single tick
// 8243 - double quote
// 8245 - back tick
// 8249 - small <
// 8250 - small >
// 8252 - !!
// 8253 - ?! joined
// 8254 - high bar
// 8255 - low bar
// 8260 - broken /
// 8263 - ??
// 8264 - ?! separate
// 8265 - !? separate
// 8364 - euro
// 8482 - TM
