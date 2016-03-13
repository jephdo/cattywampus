import os
import re
import logging
import pathlib

import botocore.session
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


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
    try:
        bucket, key = bucket_and_key_from_path(s3path)
    except ValueError:
        return False
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

    is_dir = False

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
    def filename(self):
        return pathlib.Path(self.path).parts[-1]

    def get(self):
        pass

    def download(self, filename=None):
        pass

    def head(self, lines_to_retrieve=100, chunksize=16384, line_separator='\n'):
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

    def read(self, bytes_to_download=65536, chunksize=16384):
        assert bytes_to_download > 0
        client = get_client()
        response = client.get_object(Bucket=self.bucket, Key=self.key)
        content_stream = response['Body']
        data = ''
        downloaded_bytes = 0
        while downloaded_bytes < bytes_to_download:
            chunk = content_stream.read(chunksize).decode('utf-8')
            if not chunk:
                break
            data += chunk
            downloaded_bytes += chunksize
        return data

    @classmethod
    def from_s3path(cls, s3path):
        bucket, key = bucket_and_key_from_path(s3path)
        client = get_client()
        response = client.get_object(Bucket=bucket, Key=key)
        last_modified = response['LastModified']
        size = response['ContentLength']
        storage_class = response.get('StorageClass') 
        return cls(bucket, key, last_modified, size, storage_class)

    @classmethod
    def from_dict(cls, bucket, _dict):
        key = _dict['Key']
        last_modified = _dict['LastModified']
        size = _dict['Size']
        storage_class = _dict['StorageClass']
        return cls(bucket, key, last_modified, size, storage_class)

    def __repr__(self):
        path = self.path
        filesize = self.size
        last_modified = self.last_modified.strftime('%b %d %H:%M')
        cls_name = self.__class__.__name__
        return """<class {cls_name} {path}, {filesize}, {last_modified}>""".format(**vars())


class S3Directory:
    """Representation of a directory on S3.

    """

    is_dir = True

    def __init__(self, bucket, prefix):
        self.bucket = bucket
        self.prefix = prefix

    @property
    def path(self):
        return os.path.join("s3://", self.bucket, self.prefix)

    @property
    def filename(self):
        return pathlib.Path(self.path).parts[-1] + '/'

    @property
    def truncated_path(self):
        return self.path.replace('s3://','')

    def __repr__(self):
        s3path = self.path
        cls_name = self.__class__.__name__
        return """<class {cls_name} {s3path}>""".format(s3path=self.path, cls_name=cls_name)