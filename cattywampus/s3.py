import os
import re
import logging
import pathlib

import botocore.session
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


def _bytes_to_human(_bytes):
    """Format number of bytes to a readable file size (e.g. 10.1 MB,
    13 kB, etc.)"""
    _bytes = float(_bytes)
    for units in ['Bytes', 'kB', 'MB', 'GB', 'TB']:
        if _bytes < 1000.:
            # for anything bigger than bytes round to one decimal point
            # for bytes no decimals
            if units is not 'Bytes':
                return "{:.1f} {}".format(_bytes, units)
            else:
                return "{:.0f} {}".format(_bytes, units)
        _bytes /= 1000.
    # if number of bytes is way too big just use petabytes
    return "{:,.1f}{}".format(_bytes, "PB")


def bucket_and_key_from_path(s3path):
    """Returns the bucket and key as a tuple from an S3 filepath."""
    m = re.compile("s3://([^/]+)/(.*)").match(s3path)
    if m:
        return (m.group(1), m.group(2))
    raise ValueError("Not recognizable S3 path '%s'" % s3path)


def get_client():
    session = botocore.session.get_session()
    return session.create_client('s3')


def file_exists(s3path):
    bucket, key = bucket_and_key_from_path(s3path)
    client = get_client()
    try:
        client.get_object(Bucket=bucket, Key=key)
    except ClientError:
        return False
    return True



def ls(s3path):
    client = get_client()
    bucket, prefix = bucket_and_key_from_path(s3path)
    objects = client.list_objects(Bucket=bucket, Prefix=prefix, Delimiter='/')
    
    if objects['IsTruncated']:
        raise ValueError("Returned more than (%s) objects. Increase max keys argument" 
            % objects['MaxKeys'])
    if objects['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise ValueError
    bucket = objects['Name']
    directories = [S3Directory(bucket, obj['Prefix']) for obj in objects.get('CommonPrefixes', [])]
    files = [S3File.from_dict(bucket, obj) for obj in objects.get('Contents', [])]
    return directories + files


class S3File:

    def __init__(self, bucket, key, last_modified, size, storage_class):
        self.bucket = bucket
        self.key = key
        self.last_modified = last_modified
        self.size = size
        self.storage_class = storage_class

    @property
    def path(self):
        return os.path.join("s3://", self.bucket, self.key)

    @property
    def truncated_path(self):
        return self.path.replace('s3://','')

    @property
    def filesize(self):
        return _bytes_to_human(self.size)

    @property
    def filename(self):
        return pathlib.Path(self.path).parts[-1]

    def get(self):
        pass

    def download(self, filename=None):
        pass

    def head(self, lines_to_retrieve=10, chunksize=16384, line_separator='\n'):
        client = get_client()
        response = client.get_object(Bucket=self.bucket, Key=self.key)
    
        content_stream = response['Body']
        accrued_lines = []
        unfinished_line = ''
        while len(accrued_lines) < lines_to_retrieve:
            chunk = content_stream.read(chunksize).decode('utf-8')
            # stream is no longer returning any more bytes which signals
            # end of file
            if not chunk:
                break

            lines = (unfinished_line + chunk).split(line_separator)
            unfinished_line = lines.pop()
            for line in lines:
                accrued_lines.append(line)
        # it's possible that there may be extra bytes leftover so you fetch
        # more than the desired number of lines:
        return accrued_lines[:lines_to_retrieve]

    @classmethod
    def from_s3path(cls, s3path):
        bucket, key = bucket_and_key_from_path(s3path)
        client = get_client()
        response = client.get_object(Bucket=bucket, Key=key)
        return cls(bucket, key, response['LastModified'], size=0, storage_class=None)

    @classmethod
    def from_dict(cls, bucket, _dict):
        key = _dict['Key']
        last_modified = _dict['LastModified']
        size = _dict['Size']
        storage_class = _dict['StorageClass']
        return cls(bucket, key, last_modified, size, storage_class)

    def __repr__(self):
        path = self.path
        filesize = self.filesize
        last_modified = self.last_modified.strftime('%b %d %H:%M')
        cls_name = self.__class__.__name__
        return """<class {cls_name} {path}, {filesize}, {last_modified}>""".format(**vars())


class S3Directory:
    """Representation of a directory on S3.

    """
    def __init__(self, bucket, prefix):
        self.bucket = bucket
        self.prefix = prefix

    @property
    def path(self):
        return os.path.join("s3://", self.bucket, self.prefix)

    @property
    def truncated_path(self):
        return self.path.replace('s3://','')

    def __repr__(self):
        s3path = self.path
        cls_name = self.__class__.__name__
        return """<class {cls_name} {s3path}>""".format(s3path=self.path, cls_name=cls_name)