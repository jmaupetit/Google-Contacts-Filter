# -*- coding: utf-8 -*-

import argparse
import sys
import csv
import os.path
import tablib


class GoogleContact(object):
    """docstring for GoogleContact"""

    def __init__(self, csv_path):

        self.csv_path = csv_path
        self.data = None

        # Google exports with UTF-16 encoding
        # hence, force utf-8 encoding
        self.to_utf8()

        # Parse the data
        self.parse()

    def to_utf8(self):
        """
        Write the utf-16 encoded source file to utf-8
        """
        import codecs
        base, ext = os.path.splitext(self.csv_path)
        dst_path = base + '_utf-8' + ext
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
        data = tablib.Dataset()

        with open(self.csv_path, 'rb') as csv_file:

            google_contact = csv.reader(csv_file)

            for row_num, row in enumerate(google_contact):
                if row_num == 0:
                    data.headers = row
                    continue
                data.append(row)

        self.data = data

    def filter(self):
        pass


def main(argv=None):

    # CLI
    parser = argparse.ArgumentParser(
        description='Filter exported google contacts')
    parser.add_argument('csv_path', help="Google contact CSV file")

    args = parser.parse_args()

    gcontact = GoogleContact(args.csv_path)

    return 1

if __name__ == "__main__":
    sys.exit(main())
