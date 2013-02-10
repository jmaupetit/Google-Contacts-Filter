#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Google Contacts Filter

Usage:
    gcontacts-filter.py [-eDMFhdv] [-t TAGS] CSV [-o OUTPUT]

Options:
    -t TAGS --tags=TAGS        Filtering tags (coma separated).
    -o OUTPUT --output=OUTPUT  Write filtered address book to file.
    -D --drop                  Drop duplicates
    -M --merge                 Merge duplicates
    -F --fix-emails            Fix multiple email addresses
    -h --help                  Show this screen.
    -v --verbose               Verbose mode.
    -d --debug                 Debug mode.
    -V --version               Show version.
"""

import sys
import codecs
import os.path
import logging
import re

from docopt import docopt
from tablib.core import Row, Dataset

from utils import UnicodeReader

__title__ = 'gcontact-filter'
__version__ = '0.1.1'
__author__ = 'Julien Maupetit'
__license__ = 'MIT'
__copyright__ = 'Copyright 2013 Julien Maupetit'


def format_phone(value):
    """
    Format phone numbers
    """
    # Skip spaces and parenthesis
    for char in (' ', '(', ')'):
        value = value.replace(char, '')
    # International numbers to local (french)
    value = re.sub('^0', '+33', value)
    value = re.sub(':::0', ':::+33', value)
    # Restore multiple item values
    value = value.replace(':::', ' ::: ')
    return value


def format_index(name):
    name = name.strip()
    name = name.lower()
    name = re.sub('[^a-z]', '-', name)
    return name


def merge_lists(src, dest):
    out = []
    if len(src) != len(dest):
        sys.exit('Cannot merge rows of different size')
    out = [d+' ::: '+s if s and d != s else d for s, d in zip(src, dest)]
    return out


class GoogleContactRow(Row):
    """
    Add tag methods for rows
    """

    def __init__(self, row=list(), tags=list(), headers=list(), logger=None):

        super(GoogleContactRow, self).__init__(row=row, tags=tags)
        self.headers = headers
        self.logger = logger

    def get_name(self, field='Name'):
        return self._row[self.headers.index(field)]

    def select_fields(self, pattern):
        fields = []
        for field in self.headers:
            if re.match(pattern, field):
                fields.append(field)
        return fields

    def has_fields(self, fields, tags=list(), callbacks=list()):
        """
        Check whether the current line has a data in fields. Apply
        callbacks if True and tag the line.
        """
        valid_tags = list()
        for field in fields:
            index = self.headers.index(field)
            if self._row[index].strip():
                valid_tags += tags
                for callback in callbacks:
                    self._row[index] = eval('%s("%s")' % (
                        callback, self._row[index]))
        return valid_tags

    def has_name(self):
        fields = self.select_fields('Name')
        return self.has_fields(fields, ['name'])

    def has_phone(self, callbacks=('format_phone',)):
        fields = self.select_fields('Phone [0-9]+ - Value')
        return self.has_fields(fields, ['phone'], callbacks)

    def inspect_email(self, fix=False):
        fields = self.select_fields('E-mail [0-9]+ - Value')

        has_multiple = False
        row = self._row
        for field in fields:
            index = self.headers.index(field)
            emails = [e.strip() for e in row[index].split(":::")]

            if len(emails) < 2:
                continue

            has_multiple = True
            self.logger.debug("Found multiple emails for row %s", row)

            if not fix:
                continue

            filtered_emails = []
            abort = False
            # Try to fix email
            for email in emails:
                keep = False
                while True:
                    # Prompt
                    p = u"Contact [%(name)s] - keep %(email)s (y/N)? " % {
                        'name': self.get_name(), 'email': email}
                    # Response
                    try:
                        r = raw_input(p.encode('ascii', 'ignore'))
                    except EOFError:
                        abort = True
                        print ''
                        break
                    if r.strip() == 'y':
                        keep = True
                    break
                # We keep this address
                if keep:
                    filtered_emails.append(email)
                if abort:
                    break
            # Store filtered emails
            if len(filtered_emails):
                row[index] = ' ::: '.join(filtered_emails)
            else:
                row[index] = None
            self.logger.info('[%(field)s] kept <%(emails)s> for %(name)s' % {
                'field': field,
                'emails': filtered_emails,
                'name': self.get_name()})

        return row, has_multiple

    def clean_fields(self, pattern):
        """
        Remove selected fields data
        """
        fields = self.select_fields(pattern)

        # Clean data
        for field in fields:
            index = self.headers.index(field)
            self._row[index] = ''

    def format_names(self):
        """
        Format names: TitleCase
        """
        fields = self.select_fields('.*Name.*')

        for field in fields:
            index = self.headers.index(field)
            self._row[index] = self._row[index].title()

    def standard_cleanup(self):
        """
        Cleanup non tagged fields
        """
        pattern = '|'.join(('^Address',
                            '^Group Membership',
                            '^Website',
                            '^Relation',
                            '^Birthday',
                            'Nickname',
                            '^Notes'))
        self.clean_fields(pattern)


class GoogleContact(object):
    """docstring for GoogleContact"""

    def __init__(self, csv_path,
                 drop=False, merge=False,
                 verbose=False, debug=False):

        # Set object attributes
        self.csv_path = csv_path
        self.data = None
        self.hash = ()
        self.drop = drop
        self.merge = merge
        self.verbose = verbose
        self.debug = debug

        # Tags
        self.taggers = (
            'has_name',
            'has_phone',)

        # set the logger
        self._set_logger()

        # Google exports with UTF-16 encoding
        # hence, force utf-8 encoding
        self.to_utf8()

        # Parse the data
        self.parse(taggers=self.taggers)

    def _set_logger(self):
        """
        Set up a standard console logger
        """

        # Set the logger
        self.logger = logging.getLogger('google-contact')
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
        elif self.verbose:
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.setLevel(logging.WARNING)

        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.logger.addHandler(ch)

    def to_utf8(self):
        """
        Write the utf-16 encoded source file to utf-8
        """

        base, ext = os.path.splitext(self.csv_path)
        dst_path = base + '_utf-8' + ext

        self.logger.info(
            'Will write utf-8 encoded data to file %(dst_path)s' % {
            'dst_path': dst_path}
        )

        BLOCKSIZE = 1048576  # or some other, desired size in bytes
        with codecs.open(self.csv_path, "r", "utf-16") as src_file:
            with codecs.open(dst_path, "w", "utf-8") as dst_file:
                while True:
                    contents = src_file.read(BLOCKSIZE)
                    if not contents:
                        break
                    dst_file.write(contents)
        self.csv_path = dst_path

    def is_duplicate(self, value):
        if value in self.hash:
            return True
        return False

    def parse(self, taggers=list()):
        """
        Open the csv file and dump it in a tablib.Dataset object
        """
        self.logger.info(
            'Will parse input %(csv_path)s csv file' % {
            'csv_path': self.csv_path}
        )

        data = Dataset()

        with open(self.csv_path, 'rb') as csv_file:

            google_contact = UnicodeReader(csv_file)

            for row_num, row in enumerate(google_contact):
                if row_num == 0:
                    data.headers = row
                    continue
                gRow = GoogleContactRow(headers=data.headers, row=row)
                gRow.standard_cleanup()
                gRow.format_names()
                tags = []
                for tagger in taggers:
                    tags += getattr(gRow, tagger)()
                tags = list(set(tags))

                # Get the row index
                index = format_index(gRow[data.headers.index('Name')])

                # Empty index
                # drop this row
                if not index:
                    self.logger.info(
                        'Ignored row without index (%(row_num)d)' %
                        {'row_num': row_num})
                    continue

                # Duplicate?
                if self.is_duplicate(index):
                    self.logger.info(
                        'Found duplicate row for %(name)s (num: %(row_num)d)' %
                        {'name': index, 'row_num': row_num})
                    # Drop this row
                    if self.drop:
                        self.logger.debug(
                            'Dropped duplicate row %(row_num)d' %
                            {'row_num': row_num})
                        continue

                    # Merge this row
                    if self.merge:
                        row_dst = self.hash.index(index)
                        data[row_dst] = merge_lists(gRow, data[row_dst])
                        self.logger.debug(
                            'Merged duplicate row %(row_src)d with %(row_dst)d'
                            % {'row_src': row_num, 'row_dst': row_dst})
                        continue

                self.hash += (index,)

                data.append(gRow, tags=tags)
                self.logger.debug('row %d tags %s', row_num, tags)

        self.data = data
        self.logger.debug(
            'File columns are:\n%s', "\n".join(self.data.headers))

    def filter(self, filters=list()):
        """
        We only consider rows containing data at least for one of the selected
        fields.
        """
        self.logger.info('Will filter data based on : %s', ", ".join(filters))

        self.filtered_data = self.data.filter(filters)

        self.logger.info(
            'Original data: %d rows - Filtered data: %d rows',
            len(self.data),
            len(self.filtered_data)
        )

    def inspect_email(self, fix=True):
        """
        Inspect if multiple emails have been defined for an email
        field.

        If fix, we manually select relevant email.
        """
        # Get the number of contacts to fix

        n = 0
        for row_num, row in enumerate(self.filtered_data):
            # Use our row object
            gRow = GoogleContactRow(headers=self.data.headers,
                                    row=row,
                                    logger=self.logger)
            if gRow.inspect_email(fix=False)[1]:
                n += 1

        mess = "Found %d contact(s) with multiple emails to fix\n" % n
        print >> sys.stdout, mess

        c = 0
        for row_num, row in enumerate(self.filtered_data):
            # Use our row object
            gRow = GoogleContactRow(headers=self.data.headers,
                                    row=row,
                                    logger=self.logger)
            self.filtered_data[row_num], has_multiple = gRow.inspect_email(
                fix=fix)
            if has_multiple:
                c += 1
                print >> sys.stdout, 'Fixed contact email %d on %d\n' % (c, n)

    def export(self, outFile=None):

        if not hasattr(self, 'filtered_data'):
            self.logger.error('Nothing to export')
            return

        if outFile is None:
            print >> sys.stdout, self.filtered_data.csv
            return

        oFile = open(outFile, 'w')
        oFile.write(self.filtered_data.csv)
        oFile.close()


def main(argv=None):

    # Parse command line arguments
    arguments = docopt(
        __doc__,
        version='Google Contacts Filtering %s' % __version__)

    # Parse input csv file
    gcontact = GoogleContact(
        arguments.get('CSV'),
        drop=arguments.get('--drop'),
        merge=arguments.get('--merge'),
        verbose=arguments.get('--verbose'),
        debug=arguments.get('--debug'))

    # Core part: filtering
    if arguments.get('--tags'):
        tags = arguments.get('--tags').split(',')
        if tags:
            gcontact.filter(tags)

    # Multiple email inspection
    if arguments.get('--fix-emails'):
        gcontact.inspect_email(fix=True)

    # Export data
    outFile = None
    if arguments.get('--output'):
        outFile = arguments.get('--output')
    gcontact.export(outFile=outFile)

    return 1

if __name__ == "__main__":
    sys.exit(main())
