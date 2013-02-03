#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Google Contacts Filter

Usage:
    gcontacts-filter.py [-ehdv] CSV

Options:
    -e --export     Export filtered address book.
    -h --help       Show this screen.
    -d --debug      Debug mode.
    -v --version    Show version.

"""

import sys
import csv
import codecs
import os.path
import logging
import re

from docopt import docopt
from tablib.core import Row, Dataset


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
    # Restore multiple item values
    value = value.replace(':::', ' ::: ')
    return value


class GoogleContactRow(Row):
    """
    Add tag methods for rows
    """

    def __init__(self, row=list(), tags=list(), headers=list()):

        super(GoogleContactRow, self).__init__(row=row, tags=tags)
        self.headers = headers

    def has_fields(self, fields, tags=list(), callbacks=list()):
        """
        Check whether the current line has a data in fields. Apply
        callbacks if True.
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
        fields = ('Name',)
        return self.has_fields(fields, ['name'])

    def has_phone(self, callbacks=('format_phone',)):
        fields = (
            'Phone 1 - Value',
            'Phone 2 - Value',
            'Phone 3 - Value',
        )
        return self.has_fields(fields, ['phone'], callbacks)


class GoogleContact(object):
    """docstring for GoogleContact"""

    def __init__(self, csv_path, debug=False):

        # Set object attributes
        self.csv_path = csv_path
        self.data = None
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
        else:
            self.logger.setLevel(logging.INFO)

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

            google_contact = csv.reader(csv_file)

            for row_num, row in enumerate(google_contact):
                if row_num == 0:
                    data.headers = row
                    continue
                gRow = GoogleContactRow(headers=data.headers, row=row)
                tags = []
                for tagger in taggers:
                    tags += getattr(gRow, tagger)()
                self.logger.debug('row %d tags %s', row_num, gRow.tags)
                data.append(gRow, tags=tags)

        self.data = data
        self.logger.info('File columns are:\n%s', "\n".join(self.data.headers))

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

    def export(self):

        if not hasattr(self, 'filtered_data'):
            self.logger.error('Nothing to export')
            return

        print self.filtered_data.csv


def main(argv=None):

    # Parse command line arguments
    arguments = docopt(
        __doc__,
        version='Google Contacts Filtering %s' % __version__)

    # Parse input csv file
    gcontact = GoogleContact(
        arguments.get('CSV'),
        debug=arguments.get('--debug'))

    # Core part: filtering
    gcontact.filter(['phone'])

    # Export data
    if arguments.get('--export'):
        gcontact.export()

    return 1

if __name__ == "__main__":
    sys.exit(main())
