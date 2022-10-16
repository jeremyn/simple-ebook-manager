# Simple Ebook Manager

By: [Jeremy Nation](mailto:jeremy@jeremynation.me).

![Tests badge.](https://github.com/jeremyn/simple-ebook-manager/actions/workflows/main.yml/badge.svg)

## Summary

Simple Ebook Manager is a collection of command-line tools to help you summarize the contents of an ebook (or other data file) library based on directories and files you've created about your ebooks. You can use these tools to generate either CSV files or a SQLite database, standardize the metadata files you've created or do custom processing.

Simple Ebook Manager:

* is cross-platform.
* has no extra Python dependencies or separate install process (see the next section).
* generates CSV or database output from scratch every time from your directories and files. Your data is not wrapped in a custom internal format or database.
* will not modify your ebooks in any way, though it can optionally update MD5 or SHA256 hashes for your ebook files.
* can be used for any files, not just ebooks.

Simple Ebook Manager is a good choice if:

* you want to create and organize your ebook library by hand using standard file system and text editing tools.
* you want to track changes using ordinary version control.
* your primary reason for organizing your ebooks into a library is to have a summary of your collection.

Simple Ebook Manager is not a good choice if:

* you want an all-in-one solution that handles every aspect of managing your ebooks.
* you want a GUI or you want to browse your ebooks by cover.
* you want your ebook manager to modify or otherwise process your ebook files: update metadata inside your ebooks, convert format, transfer to a device or upload to a cloud service.

## Installation

There are no requirements other than Python 3.10 or greater and a recent version of the external SQLite library if your installed Python uses one. (This generally means Linux, and if your distribution provides Python 3.10 or greater, the SQLite library provided along with it should be recent enough.)

You don't need any external Python packages and there is no install script. Just clone the repository, read the documentation and go.

## Quickstart Example

This section demonstrates basic usage with an example ebook library by first looking at that library and then walking through the four *commands*: `clean`, `csv`, `custom` and `db`. All program examples run from the repository root. For simplicity, each example will start with `ebooks`, but you may need to pass this to your local Python 3.10+ interpreter, for example as "`python3 ebooks ...`" or "`py ebooks ...`".

You need to create the necessary directories and files before using Simple Ebook Manager. For this quickstart we will use the example [`tests/files/example_library_dir`](tests/files/example_library_dir/) in this repository, which looks like this:

```
example_library_dir/
├── schema.json
├── Pride and Prejudice/
│   ├── description.txt
│   ├── metadata.json
│   ├── Pride and Prejudice.epub
│   └── Pride and Prejudice.pdf
└── Wonderful Wizard of Oz, The/
    ├── description.txt
    ├── metadata.json
    ├── The Wonderful Wizard of Oz.epub
    └── The Wonderful Wizard of Oz.txt
```

Here we have one *library dir* named `example_library_dir`, one *schema file* named `schema.json` at the base of the library dir, and two *book dirs*, each of which contains a *metadata file* named `metadata.json`, and a `description.txt` text file. In each book dir we have EPUB/PDF/etc *book files*, though in this specific case all the book files are just short placeholder text files regardless of their extension. Finally, in this README a *book* is the logical entity defined by all the files in a book dir and doesn't refer to any particular book file.

Suppose you created this library dir and the various JSON and text files by hand but they're not very tidy, maybe the indentation is irregular and the keys are in different orders between the files, and you want to reformat your files in a standard way. You also want to check the MD5 or SHA256 hashes that you put into the metadata files for your book files. You run:

```console
$ ebooks clean --library-dirs tests/files/example_library_dir/ --update-hash
```

which makes and reports changes as appropriate. Since you are running this against files included in this repository, there should be no changes.

That done, you now want to create a spreadsheet with information about your books. You want the output to go to `/tmp`. You run:

```console
$ ebooks csv --library-dirs tests/files/example_library_dir/ --output-dir /tmp
```

which creates the file `/tmp/books.csv`. You can also include a `--split` option to generate multiple CSV files to put into a multi-worksheet spreadsheet with cross-references between books and other fields, for example between books and authors. For our example library dir and schema file, the `--split` option will create files `authors.csv`, `book_files.csv` and `books.csv`.

You also want to create a [SQLite](https://www.sqlite.org/index.html) database about your library. You run:

```console
$ ebooks db --library-dirs tests/files/example_library_dir/ --output-dir /tmp
```

which creates a file `/tmp/books.db` that you can inspect with SQLite tools such as the [`sqlite3`](https://www.sqlite.org/cli.html) program available on many platforms. The database has appropriate tables and views including a comprehensive `v_summary` view.

Finally, you want to edit all the metadata files in your library, for example by adding a new field, so you write a custom Python module `my_code.py` to do this and run:

```console
$ ebooks custom --library-dirs tests/files/example_library_dir/ --user-module my_code.py
```

That's the basic functionality for the four commands. You can run each command with just `--help` to get more information about that command. The rest of this documentation describes the necessary files and details about the commands.

## Files

In this section we look at how Simple Ebook Manager expects you to organize your files. Because there is no GUI or setup wizard, you must build your libraries yourself, so it's important you know what they should contain.

The `.json` metadata and schema files are standard [JSON](https://www.json.org) files and will be described using terms such as strings, booleans, key-value pairs, arrays of objects and so on.

### Directories

The basic library dir layout and files were mentioned in the quickstart above.

Library dirs can have any names supported by your file system. A subdirectory in a library dir will be processed as a book dir if the subdirectory's name doesn't start with a "`.`", that is, it's not a hidden directory like `.git`, and if the subdirectory contains a file named `metadata.json`. Otherwise book dirs can have any names supported by your file system. You might find it convenient to give a book dir the `sort` value of that book's `title`, discussed below.

### schema.json

The schema file describes the expected field names and field types in your metadata files. This structure should be unique across all books processed in a single run. By default Simple Ebook Manager will look for a `schema.json` file at the base of your library dirs, but you can also provide a specific file. If you don't provide a schema file and have multiple library dirs, at least one of the library dirs must have a schema file named `schema.json`, and all schema files in the library dirs must logically match.

The keys in the example schema file at [`tests/files/example_library_dir/schema.json`](tests/files/example_library_dir/schema.json), such as `book_title` and `authors`, correspond to keys in the metadata files. The values such as `title` and `sortdisplay` describe the field types, discussed below. The order of the keys in the schema file determines the column order in the CSV and DB files.

Every key in the schema file must appear in the metadata file, with the exception of non-inline strings, discussed below, but any field value may be null in the metadata file except as otherwise noted below.

### metadata.json

The metadata file describes the metadata for a book, such as the book's title or authors. It must be named `metadata.json`. The required field names and types are described in the schema file. Unlike the schema file, the order of fields in the metadata file has no effect on the CSV or DB output.

### Fields

In this section we discuss the different field types supported by Simple Ebook Manager.

In the schema file, some fields are defined simply by their type as a string, while others require more information and so are defined as objects. Examples are included for types that require an object definition.

In some cases, there are different ways to represent the same logical information in a metadata file:

* An array with one element can be replaced with just the element.
* Empty arrays or objects (but not empty strings) can be replaced with null.
* `sortdisplay` objects can be replaced with a string if their `display` and `sort` values match, discussed below.

The clean command will simplify field values where possible, so you don't need to worry about getting it exactly right when you create your files.

Simple Ebook Manager supports the following field types.

#### date

A `date` field has a string value in the metadata file that matches a format with [strftime/strptime codes](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) in the schema file. In our example schema file, we have:

```json
"date_published": {
    "type": "date",
    "input_format": "%Y-%b-%d",
    "output_format": "%Y-%m-%d"
}
```

`input_format` describes how the date is given in the metadata file and `output_format` describes how it should be written to the CSV/DB output. In the *Pride and Prejudice* metadata file we have:

```json
"date_published": "1813-Jan-28"
```

which matches the `%Y-%b-%d` input format. This date written to CSV/DB output would be `1813-01-28`, matching the `%Y-%m-%d` output format.

Simple Ebook Manager uses the [`datetime`](https://docs.python.org/3/library/datetime.html) module for date support, which [doesn't support years less than 1](https://docs.python.org/3/library/datetime.html#datetime.MINYEAR). A possible workaround is to using an inline `string` field, discussed below, instead of `date`, if you are willing to give up the ability to reformat your date on output.

#### file

The `file` field describes the book files associated with a given book. There must always be exactly one `file` field, and it can't be empty or null.

In our example schema file, the field name for our `file` field is `book_files`, so in the *Pride and Prejudice* metadata file we have:

```json
"book_files": [
    {
        "directory": ".",
        "hash": "md5:6c1fce7eeb895b7821f5b56e7a9f2da1",
        "name": "Pride and Prejudice.epub"
    },
    {
        "directory": ".",
        "hash": "md5:42b12a9921f1c14f0c81e3d42e5d58ff",
        "name": "Pride and Prejudice.pdf"
    }
]
```

This describes two book files, an EPUB and a PDF, in an array.

The `name` value is the base name for each book file without the directory. Each name must be unique for a given book.

The `hash` value is the MD5 or SHA256 hash of that file, prefixed with `md5:` or `sha256:` depending on the algorithm. This can be updated (but not added) with the clean command.

The `directory` value is the directory containing the book file. This can be relative or absolute. A relative path will be relative to the book dir. You can omit `directory`, in which case the assumed default is `"."`, meaning the file is in the book dir with the metadata file, and this will be added by the clean command.

##### Dir Vars

The `directory` field also supports *dir vars*, which are variables that you can enter when you run most commands. They are defined with curly brackets, so for example if you have a `directory` value `"{var1}/Pride and Prejudice"` for a book file and pass `--dir-var var1 /my/dir` to a command that accepts dir vars, then Simple Ebook Manager will replace `{var1}` with `/my/dir` and consider that book file's directory to be `/my/dir/Pride and Prejudice`.

You can use multiple dir vars in the same `directory`, for example `"{var1}{var2}Pride and Prejudice"`. In this case you should pass the `--dir-var` (or `-d`) option twice: `-d var1 /my -d var2 /dir`. You can also have different dir vars for different book files, for example `{var1}` for one book file and `{var2}` for another. All dir vars are replaced at once for each book file, so you cannot have nested dir vars.

Once a book has a dir var, then that dir var must be defined in any processing done for that book. Simple Ebook Manager will error if it finds an undefined dir var.

#### keyvalue

`keyvalue` fields are key-value pairs in a single object. They can be used to store related text information for a book, for example IDs or ratings from different sources.

In our example schema file, we have:

```json
"ids": {
    "type": "keyvalue",
    "key_label": "id_type",
    "value_label": "id_value"
}
```

The values for `key_label` and `value_label` are used for column names in the DB output.

In the metadata file for *Pride and Prejudice* we have:

```json
"ids": {
    "ISBN": "978-pride-and-prejudice",
    "URI": "https://example.com"
}
```

The `keyvalue` field as a whole may be null, though any key found must have a string value.

#### sortdisplay

`sortdisplay` fields are used when you want to cross-reference books and other entities such as authors. For example, with an "`authors`" `sortdisplay` field you can list multiple authors for a book, and the same author for multiple books, and the csv and db commands can extract this information into a separate `authors` file or table with references between books and authors.

The basic `sortdisplay` value has two forms. The first form is an object with two keys: `display` and `sort`. Simple Ebook Manager will sort on the `sort` value whenever sorting needs to happen. (This is why the field type isn't "displaysort".) The example schema file has `"authors": "sortdisplay"` and the *Pride and Prejudice* metadata file has:

```json
"authors": {
    "display": "Jane Austen",
    "sort": "Austen, Jane"
}
```

The second basic form for `sortdisplay` is a string, for when the `display` and `sort` values would be the same. A book by the poet Homer would have simply:

```json
"authors": "Homer"
```

`sortdisplay` can also be an array with multiple elements, themselves either `sortdisplay` objects or strings. If Jane Austen and Homer wrote a book together, we would have:

```json
"authors": [
    {
        "display": "Jane Austen",
        "sort": "Austen, Jane"
    },
    "Homer"
]
```

Partial duplicates, where two `sortdisplay` objects have the same `display` value but different `sort` values or vice versa, whether in the same book or between books, are not allowed.

#### string

`string` values are text fields and can be either `inline` or not.

##### inline

Inline `string` field values are written directly in the metadata file.

In our example schema file, we have:

```json
"subtitle": {
    "type": "string",
    "inline": true
}
```

and in the *Pride and Prejudice* metadata file we have:

```json
"subtitle": "A Novel in Three Volumes"
```

##### non-inline

Non-inline `string` field values are written in separate text files in the book dir. They should be used when a long text value, possibly with paragraphs or other formatting, would be awkward to put directly in a JSON file.

The name of the text file should match the name of the field. In our example schema file, we have:

```json
"description": {
    "type": "string",
    "inline": false
}
```

In this case we expect a text file in the book dir named `description.txt`. If this file is missing, that is the same as the value being null.

You can't mix a field as both inline and not: if inline, the field must be in the metadata file for every book, as a string or null, and if not inline, in a separate file or missing.

The clean command has some special processing for these files, discussed below.

#### title

The `title` field is for the book's actual title and uniquely identifies a book across all library dirs. Like the `file` field, there must always be exactly one `title` field, and it can't be empty or null. Like `sortdisplay`, the `title` can be either an object with `display` and `sort` keys, or a string if those values would be the same. Neither partial nor complete duplicates are allowed across books.

In our example schema file, we have `"book_title": "title"` and in the *Pride and Prejudice* metadata file we have:

```json
"book_title": "Pride and Prejudice"
```

while in the *The Wonderful Wizard of Oz* metadata file we have:

```json
"book_title": {
    "display": "The Wonderful Wizard of Oz",
    "sort": "Wonderful Wizard of Oz, The"
}
```


## Commands

There are four commands in Simple Ebook Manager: `clean`, `csv`, `custom` and `db`. Each command takes its own options though some options are common to some or all of the commands. Each command is run as `ebooks COMMAND OPTIONS`. Run `ebooks COMMAND --help` for detailed usage information.

### clean

The `clean` command standardizes metadata and non-inline string text files.

The clean command will not ask for confirmation before modifying a file and it will only report that a file has changed, not what changed in the file. It's safest to keep your library dirs under version control so you can check the results before committing any changes.

The clean command will try to standardize newlines for all your metadata and text files to be the same type, either POSIX (`\n`) or Windows (`\r\n`). You can supply the specific type of newline you want to the `--newline` option, otherwise without the option it will attempt to guess what you want and apply that guess to all files. If you know your library has mixed newlines, you should supply the specific type you want rather than let the clean command guess.

#### metadata file

For the metadata file, the clean command will standardize the layout, change newlines if necessary, clean up whitespace and:

* add `directory: "."` to any file objects missing a directory.
* alphabetize the keys.
* simplify logical values where possible as discussed in the fields section above.
* update MD5 or SHA256 hashes (requires `--update-hash`).

With the `--update-hash` option, the command will calculate the MD5 or SHA256 hash for each book file and update the book's metadata file if the hash doesn't match. Calculating a hash is the only time Simple Ebook Manager interacts directly with book files. You can supply the specific algorithm to the option, or, if you include the option without an algorithm as we did in the quickstart above, the command will try to guess your preferred algorithm and apply that same guess to all book files.

#### non-inline string text file

For non-inline string text files, the clean command will clean up whitespace, change newlines if necessary and:

* add a title prefix to each file if not already present.
* replace certain Unicode symbols with ASCII equivalents (requires `--replace-unicode`).

The title prefix is based on the book title's `display` value. For *Pride and Prejudice* the title prefix is:

```
# Title: Pride and Prejudice
#
```

If this exact text is not already present at the start of the file, it will be added. The title prefix is not otherwise checked by Simple Ebook Manager, but it might be useful to you if the text file is somehow separated from the book dir. In practice, because the clean command is sensitive to the exact text in the title prefix, it's best to let the clean command add the prefix itself for new files.

With the `--replace-unicode` option, the clean command will replace certain Unicode symbols with ASCII equivalents, for example curly double quotes `“` and `”` with the straight double quote `"`. An expected use for these text files is to contain extended descriptions of books where these descriptions may be copied from elsewhere already containing these symbols. Replacing the symbols with ASCII equivalents might make it easier to work with the text. The replacement logic is specific to certain symbols, meaning the clean command will not replace non-ASCII symbols generally. You can find the list of changes in [`src/book/book.py`](src/book/book.py).

### csv

The `csv` command produces CSV files with information collected from the book metadata. It will overwrite existing output files without asking for confirmation.

There are two modes for this command, controlled with the `--split` option. Non-split mode, the default without this option, will create a single CSV file `books.csv` with information about your books. Split mode will create multiple CSV files with cross-references that can be added as worksheets in a single spreadsheet. Split mode will create one main `books.csv` file, one CSV file for the `file` field, and one CSV file for each `sortdisplay` field.

Using split mode with `example_library_dir`, the csv command will generate three files: `authors.csv`, `book_files.csv` and `books.csv`. You can then import these files into the same spreadsheet in three worksheets with sheetnames `authors`, `book_files` and `books`. The details for doing this will depend on your spreadsheet software. Once that's done:

* the primary `books` worksheet will refer to `sortdisplay` worksheets for appropriate values, so that for example changing an author's name in the `authors` worksheet will change the author's name in the `books` worksheet.
* the `books` worksheet will pull a book file's hash value from the `file` worksheet, and the `file` worksheet will pull title information from the `books` worksheet.

Split mode will add keys to the CSV files for lookups between worksheets. By default these are ascending integers, but you can instead generate [UUID4](https://en.wikipedia.org/wiki/Universally_unique_identifier) keys with the `--use-uuid-key` option. This has no effect on the spreadsheet functionality, but you may prefer one type of key or the other if you decide to use and maintain a split CSV spreadsheet as your primary reference after creating it with Simple Ebook Manager.

### custom

The `custom` command lets you do bulk edits and data collection across your book dirs. This is what to use if you need to add or edit fields in all your metadata and text files and report how many changes were made.

Other than specifying library dirs, the only required option is `--user-module`. This option should take a Python file containing a `process` function with a particular signature. See [`tests/files/user_files/example_user_module.py`](tests/files/user_files/example_user_module.py) for more details, including how to accept extra options in your custom code.

### db

The `db` command produces a SQLite database with book information. The command will overwrite an existing database file without asking for confirmation. Once created, you can inspect the database with SQLite tools such as the `sqlite3` program available on many platforms.

The book data is joined in reasonable ways, and a number of views are available for more convenient browsing. In particular, a `v_summary` view is available which provides a thorough description of each book.

The db command accepts a `--user-sql-file` option where you can pass in your own SQL file to run after the database is created. There is also the `--use-uuid-key` option which, as with the csv command, causes the database to use UUID4 keys instead of the default integer keys.

## Development

This section has some comments on Simple Ebook Manager development.

### Issues and Pull Requests

While I hope that Simple Ebook Manager is useful to others, it's primarily a personal project. To avoid licensing and ownership issues, I will not accept PRs or patches.

Bug reports for existing functionality or suggestions on improving accessibility or internationalization are welcome although I may not act on them or even respond. Other requests to add new features or refactor the internals are even less likely to result in changes.

### Dev Environment

The included [`requirements-dev.txt`](requirements-dev.txt) contains some basic pip packages used for development. [`pyproject.toml`](pyproject.toml) has some default configuration.

### Testing

There are many tests included in the [`tests`](tests/) directory. You can run them with:

```console
$ python3 -m unittest discover tests/
```

from the repository root.

## License

Copyright [Jeremy Nation](mailto:jeremy@jeremynation.me).

Licensed under the GNU Affero General Public License (AGPL) v3. See the included [`LICENSE`](LICENSE) file for the full license text.
