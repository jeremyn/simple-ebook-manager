BEGIN TRANSACTION;
CREATE TABLE authors (
    pkey INT PRIMARY KEY,
    sort TEXT UNIQUE NOT NULL,
    display TEXT UNIQUE NOT NULL
);
INSERT INTO "authors" VALUES(1,'Author1, CompleteExample','CompleteExample Author1');
INSERT INTO "authors" VALUES(2,'Author2, CompleteExample','CompleteExample Author2');
INSERT INTO "authors" VALUES(3,'CompressedFieldsExampleAuthor','CompressedFieldsExampleAuthor');
CREATE TABLE book (
    pkey INT PRIMARY KEY,
    metadata_directory TEXT UNIQUE NOT NULL,
    book_title_sort TEXT UNIQUE NOT NULL,
    book_title_display TEXT UNIQUE NOT NULL,
    subtitle TEXT,
    date_published TEXT,
    description TEXT
);
INSERT INTO "book" VALUES(1,'/placeholder_library_dir/Compressed Fields Example','CompressedFieldsExampleTitle','CompressedFieldsExampleTitle',NULL,'2000-01-31','This book has single word SortDisplay fields.
');
INSERT INTO "book" VALUES(2,'/placeholder_library_dir/Complete Example','Example, Complete','Complete Example','CompleteExample subtitle 😀','2000-01-31','This book has all metadata fields filled and a non-ASCII subtitle and description 😀.
');
INSERT INTO "book" VALUES(3,'/placeholder_library_dir/Minimal Example','Example, Minimal','Minimal Example',NULL,NULL,NULL);
INSERT INTO "book" VALUES(4,'/placeholder_library_dir/Overlap Example','Example, Overlap','Overlap Example','OverlapExample subtitle','2000-01-31','This book overlaps metadata with both Complete Example and Compressed Fields Example.
');
CREATE TABLE book_authors (
    book_pkey INT REFERENCES book(pkey),
    authors_pkey INT REFERENCES authors(pkey),
    PRIMARY KEY (book_pkey, authors_pkey)
) WITHOUT ROWID;
INSERT INTO "book_authors" VALUES(1,3);
INSERT INTO "book_authors" VALUES(2,1);
INSERT INTO "book_authors" VALUES(2,2);
INSERT INTO "book_authors" VALUES(4,1);
INSERT INTO "book_authors" VALUES(4,3);
CREATE TABLE book_book_files (
    book_pkey INT REFERENCES book(pkey),
    file_name TEXT UNIQUE NOT NULL,
    file_hash TEXT UNIQUE NOT NULL,
    file_full_path TEXT UNIQUE NOT NULL,
    metadata_directory TEXT NOT NULL,
    file_directory TEXT NOT NULL,
    dir_vars TEXT,
    PRIMARY KEY (book_pkey, file_name)
) WITHOUT ROWID;
INSERT INTO "book_book_files" VALUES(1,'Compressed Fields Example.txt','md5:f5ac42efafd896f3586dad942dc43a9a','/placeholder_library_dir/Compressed Fields Example/Compressed Fields Example.txt','/placeholder_library_dir/Compressed Fields Example','.','name1=.;name2=.');
INSERT INTO "book_book_files" VALUES(2,'Complete Example.1.txt','md5:26c550676705b779f180c3baa4b02a36','/placeholder_library_dir/Complete Example/Complete Example.1.txt','/placeholder_library_dir/Complete Example','{name1}/{name2}','name1=.;name2=.');
INSERT INTO "book_book_files" VALUES(2,'Complete Example.2.txt','md5:acfb87d35ea9685c1346c50f7920c04a','/placeholder_library_dir/Complete Example/Complete Example.2.txt','/placeholder_library_dir/Complete Example','{name1}/{name2}','name1=.;name2=.');
INSERT INTO "book_book_files" VALUES(3,'Minimal Example.txt','md5:6288fd0c77d28fe3e4ff34f13042e1bc','/placeholder_library_dir/Minimal Example/Minimal Example.txt','/placeholder_library_dir/Minimal Example','.','name1=.;name2=.');
INSERT INTO "book_book_files" VALUES(4,'Overlap Example.txt','md5:a6aceb15816f6f7e73aa01c41c9cec09','/placeholder_library_dir/Overlap Example/Overlap Example.txt','/placeholder_library_dir/Overlap Example','.','name1=.;name2=.');
CREATE TABLE book_ids (
    book_pkey INT REFERENCES book(pkey),
    id_type TEXT NOT NULL,
    id_value TEXT NOT NULL,
    PRIMARY KEY (book_pkey, id_type)
) WITHOUT ROWID;
INSERT INTO "book_ids" VALUES(2,'ISBN','978-complete-example');
INSERT INTO "book_ids" VALUES(2,'URI','https://example.com');
INSERT INTO "book_ids" VALUES(4,'ISBN','978-overlap-example');
CREATE TABLE user_sql_table (pkey INT PRIMARY KEY);
INSERT INTO "user_sql_table" VALUES(1);
CREATE VIEW v_book_authors AS
SELECT
    book.pkey || ':' || authors.pkey AS unique_key,
    book.book_title_sort AS book_title_sort,
    book.book_title_display AS book_title_display,
    authors.sort AS authors_sort,
    authors.display AS authors_display
FROM
    book,
    book_authors,
    authors
WHERE
    book.pkey=book_authors.book_pkey AND
    book_authors.authors_pkey=authors.pkey
ORDER BY
    book.book_title_sort,
    authors.sort;
CREATE VIEW v_book_book_files AS
SELECT
    book.pkey || ':' || book_book_files.file_name AS unique_key,
    book.book_title_sort AS book_title_sort,
    book.book_title_display AS book_title_display,
    book_book_files.file_name,
    book_book_files.file_hash,
    book_book_files.file_full_path,
    book_book_files.metadata_directory,
    book_book_files.file_directory,
    book_book_files.dir_vars
FROM
    book,
    book_book_files
WHERE
    book.pkey=book_book_files.book_pkey
ORDER BY
    book.book_title_sort,
    book_book_files.file_name;
CREATE VIEW v_book_ids AS
SELECT
    book.pkey || ':' || book_ids.id_type AS unique_key,
    book.book_title_sort AS book_title_sort,
    book.book_title_display AS book_title_display,
    book_ids.id_type,
    book_ids.id_value
FROM
    book,
    book_ids
WHERE
    book.pkey=book_ids.book_pkey
ORDER BY
    book.book_title_sort,
    book_ids.id_type;
CREATE VIEW v_summary AS
WITH
authors_concat AS (
    SELECT DISTINCT
        book_pkey,
        group_concat(authors_sort, ';') OVER (
            PARTITION BY
                book_pkey
            ORDER BY
                authors_sort
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS authors_sort,
        group_concat(authors_display, ';') OVER (
            PARTITION BY
                book_pkey
            ORDER BY
                authors_display
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS authors_display
    FROM (
        SELECT
            book.pkey AS book_pkey,
            authors.sort AS authors_sort,
            authors.display AS authors_display
        FROM
            book,
            book_authors,
            authors
        WHERE
            book.pkey=book_authors.book_pkey AND
            book_authors.authors_pkey=authors.pkey
    )
),
book_files_concat AS (
    SELECT DISTINCT
        book_pkey,
        group_concat(book_book_files_combined, ';') OVER (
            PARTITION BY
                book_pkey
            ORDER BY
                book_book_files_combined
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS book_files
    FROM (
        SELECT
            book.pkey AS book_pkey,
            book_book_files.file_name || '::' || book_book_files.file_hash AS book_book_files_combined
        FROM
            book,
            book_book_files
        WHERE
            book.pkey=book_book_files.book_pkey
    )
),
ids_concat AS (
    SELECT DISTINCT
        book_pkey,
        group_concat(book_ids_combined, ';') OVER (
            PARTITION BY
                book_pkey
            ORDER BY
                book_ids_combined
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS ids
    FROM (
        SELECT
            book.pkey AS book_pkey,
            book_ids.id_type || ':' || book_ids.id_value AS book_ids_combined
        FROM
            book,
            book_ids
        WHERE
            book.pkey=book_ids.book_pkey
    )
)
SELECT
    book.pkey AS book_pkey,
    book.metadata_directory,
    book.book_title_sort,
    book.book_title_display,
    book.subtitle,
    authors_concat.authors_sort,
    authors_concat.authors_display,
    book_files_concat.book_files,
    ids_concat.ids,
    book.date_published,
    book.description
FROM
    book
LEFT OUTER JOIN
    authors_concat
    ON
    book.pkey=authors_concat.book_pkey
LEFT OUTER JOIN
    book_files_concat
    ON
    book.pkey=book_files_concat.book_pkey
LEFT OUTER JOIN
    ids_concat
    ON
    book.pkey=ids_concat.book_pkey
GROUP BY
    book.book_title_sort
ORDER BY
    book.book_title_sort;
CREATE VIEW v_user_sql_view AS SELECT * FROM book;
COMMIT;
