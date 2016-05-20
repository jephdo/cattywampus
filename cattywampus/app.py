from datetime import datetime

from flask import Flask, Response, render_template, abort, redirect, url_for
from flask.ext.bootstrap import Bootstrap

from .filters import format_date, format_time, timesince, bytes_to_human
from .s3 import ls, get_client, file_exists, S3File, bucket_and_key_from_path, partition_objects

from config import Config


app = Flask(__name__)
app.jinja_env.filters['format_date'] = format_date
app.jinja_env.filters['format_time'] = format_time
app.jinja_env.filters['timesince'] = timesince
app.jinja_env.filters['bytes_to_human'] = bytes_to_human

app.debug = True


Bootstrap(app)


def validate_path(path):
    if not path.startswith('s3://'):
        path = 's3://' + path
    return path

def get_url_for_parent_dir(path):
    if path.endswith('/'):
        path = path[:-1]
    parent_dir = '/'.join(path.split('/')[:-1]) + '/'
    return url_for('list_files', path=parent_dir.replace('s3://',''))


@app.errorhandler(404)
def show_404(error):
    return render_template('404.html'), 404


@app.route('/')
def show_buckets():
    response = get_client().list_buckets()
    buckets = response['Buckets']
    # return str(buckets)
    return render_template('buckets.html', buckets=buckets, now=datetime.now())

@app.route('/s3://<path:path>')
def redirect_urls_prefixed_s3(path):
    # I want people to be able to directly enter in s3 paths into the url
    # but I don't want that to be the official url. I.e. I will redirect a 
    # request from `app.com/s3://br-user/jeph/tmp/` to `app.com/br-user/jeph/tmp/`
    return redirect(url_for('list_files', path=path))


@app.route('/download/<path:path>')
def download_file(path):
    path = validate_path(path)
    # Check
    # 1) you can't download a directory (it ends with a /), so resource doesn't exist
    # 2) check if the file/key exists on s3, if it doesn't page shouldn't exist
    if path.endswith('/') or not file_exists(path):
        abort(404)

    bucket, key = bucket_and_key_from_path(path)
    filename = key.split('/')[-1]
    content_stream = get_client().get_object(Bucket=bucket, Key=key)['Body']

    def stream():
        while True:
            chunk = content_stream.read(Config.STREAM_CHUNK_SIZE) 
            if not chunk:
                break
            yield chunk

    response = Response(stream())
    response.headers['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


@app.route('/sample/<path:path>')
def sample_file(path):
    path = validate_path(path)
    if path.endswith('/') or not file_exists(path):
        abort(404)
    file = S3File.from_s3path(path)
    head = '\n'.join(file.sample(n=10))
    shown_size = len(head.encode())
    return render_template('preview.html', file=file, head=head, shown_size=shown_size,
        parent_dir_url=get_url_for_parent_dir(path), now=datetime.now())


@app.route('/<path:path>')
def list_files(path):
    path = validate_path(path)
    # if the path ends with a / then assume it's a directory (i.e. prefix)
    # otherwise assume that this is a file so check it exists and possibly do a head
    # on the file
    if path.endswith('/'):
        # since it ends in slash, the last part is an empty string ''
        dirname = path.split('/')[-2]  
        objects = ls(path)
        files, dirs = partition_objects(objects)
        dirstats = dict(
            numdirs=len(dirs),
            numfiles=len(files),
            total_filesize=sum(f.size for f in files)
        )
        # if there's no files in the directory then there are no keys under this
        # prefix so this directory doesn't exist i.e. 404
        if not objects:
            abort(404)
        return render_template('files.html', path=path, objects=objects, 
            dirname=dirname, dirstats=dirstats,
            parent_dir_url=get_url_for_parent_dir(path), now=datetime.now())
    else:
        if file_exists(path):
            return preview_file(path)
        else:
            abort(404)


def preview_file(path):
    file = S3File.from_s3path(path)
    head = file.read(Config.PREVIEW_CHUNK_SIZE, Config.PREVIEW_CHUNK_SIZE)
    shown_size = Config.PREVIEW_CHUNK_SIZE if Config.PREVIEW_CHUNK_SIZE < file.size else file.size
    return render_template('preview.html', file=file, head=head, shown_size=shown_size,
        parent_dir_url=get_url_for_parent_dir(path), now=datetime.now())
    # make it look like the github page
    # show meta data: filename | 4.99 kb | last modified
    # https://github.com/boto/botocore/blob/develop/docs/make.bat

