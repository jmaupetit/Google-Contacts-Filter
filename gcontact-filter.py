#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Google Contacts Filter

Usage:
    gcontacts-filter.py [-ehv] CSV

Options:
    -e --export     Export filtered address book.
    -h --help       Show this screen.
    -v --version    Show version.

"""

import sys
import csv
import codecs
import os.path
import logging
import copy

from docopt import docopt
from tablib.core import Row, Dataset


class GoogleContactRow(Row):
    """
    Add tag methods for rows
    """

    def __init__(self, row=list(), tags=list(), headers=list()):

        super(GoogleContactRow, self).__init__(row=row, tags=tags)
        self.headers = headers

    def has_fields(self, fields):
        for field in fields:
            index = self.headers.index(field)
            if self._row[index].strip():
                return True
        return False

    def has_name(self):
        fields = ('Name',)
        return self.has_fields(fields)

    def has_phone(self):
        fields = (
            'Phone 1 - Value',
            'Phone 2 - Value',
            'Phone 3 - Value',
        )
        return self.has_fields(fields)


class GoogleContactDataset(Dataset):
    """
    Google Contact Dataset

    Add tag methods for Dataset rows
    """

    def __init__(self, *args, **kwargs):

        super(GoogleContactDataset, self).__init__(*args, **kwargs)
        self._data = list(GoogleContactRow(arg) for arg in args)

    def __setitem__(self, key, value):
        self._validate(value)
        self._data[key] = GoogleContactRow(value)


class GoogleContact(object):
    """docstring for GoogleContact"""

    def __init__(self, csv_path):

        # set the logger
        self._set_logger()

        # Set object attributes
        self.csv_path = csv_path
        self.data = None

        # Google exports with UTF-16 encoding
        # hence, force utf-8 encoding
        self.to_utf8()

        # Parse the data
        self.parse()

    def _set_logger(self):
        """
        Set up a standard console logger
        """

        # Set the logger
        self.logger = logging.getLogger('google-contact')
        self.logger.setLevel(logging.DEBUG)

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

    def parse(self):
        """
        Open the csv file and dump it in a tablib.Dataset object
        """
        self.logger.info(
            'Will parse input %(csv_path)s csv file' % {
            'csv_path': self.csv_path}
        )

        data = GoogleContactDataset()

        with open(self.csv_path, 'rb') as csv_file:

            google_contact = csv.reader(csv_file)

            for row_num, row in enumerate(google_contact):
                if row_num == 0:
                    data.headers = row
                    continue
                data.append(row)

        self.data = data
        self.logger.info('File columns are:\n%s', "\n".join(self.data.headers))

    def delete_empty_columns(self):
        """
        Delete empty columns to speed up data manipulation
        """
        self.logger.info('Will delete empty columns')

        self.filtered_data = copy.copy(self.data)

        for column in self.data.headers:
            if not len([val for val in self.data[column] if val]):
                self.logger.debug('Will delete column %s', column)
                del(self.filtered_data[column])

    def filter(self, filters=list()):
        """
        We only consider rows containing data at least for one of the selected
        fields.
        """
        self.logger.info('Will filter data based on : %s', ", ".join(filters))

        filtered_data = GoogleContactDataset()
        filtered_data.headers = copy.copy(self.filtered_data.headers)

        for index, row in enumerate(self.filtered_data._data):
            skip = True
            gRow = GoogleContactRow(headers=filtered_data.headers, row=row)

            # Apply filters
            for _filter in filters:
                # This row contains data for selected field
                if getattr(gRow, _filter)():
                    skip = False
                    break
            if skip:
                self.logger.debug('Skip filtered row %d', index)
                continue

            filtered_data.append(gRow)

        self.filtered_data = filtered_data

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
    arguments = docopt(__doc__, version='Google Contacts Filtering 0.1')

    # Parse input csv file
    gcontact = GoogleContact(arguments.get('CSV'))

    # Delete empty columns
    gcontact.delete_empty_columns()

    # Core part: filtering
    gcontact.filter((
        'has_name',
        'has_phone'
    ))

    # Export data
    if arguments.get('--export'):
        gcontact.export()

    return 1

if __name__ == "__main__":
    sys.exit(main())
