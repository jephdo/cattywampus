from datetime import datetime, date
import pytz


from flask import Flask, Response, render_template, abort, redirect, url_for
from flask.ext.bootstrap import Bootstrap

from .s3 import ls, get_client, file_exists, S3File, bucket_and_key_from_path


app = Flask(__name__)
app.debug = True

Bootstrap(app)


def validate_path(path):
    if not path.startswith('s3://'):
        path = 's3://' + path
    return path


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
    # you can't download a directory, so resource doesn't exist
    if path.endswith('/'):
        abort(404)
    # check if the file/key exists on s3, if it doesn't page shouldn't exist
    if not file_exists(path):
        abort(404)

    bucket, key = bucket_and_key_from_path(path)
    content_stream = get_client().get_object(Bucket=bucket, Key=key)['Body']

    def stream():
        while True:
            chunk = content_stream.read(262144) # stream at 256 kb
            if not chunk:
                break
            yield chunk

    return Response(stream())


@app.route('/<path:path>')
def list_files(path):
    path = validate_path(path)
    # if the path ends with a / then assume it's a directory (i.e. prefix)
    # otherwise assume that this is a file so check it exists and possibly do a head
    # on the file
    if path.endswith('/'):
        objects = ls(path)
        # if there's no files in the directory then there are no keys under this
        # prefix so this directory doesn't exist i.e. 404
        if not objects:
            abort(404)
        return render_template('files.html', path=path, objects=objects, now=datetime.now())
    else:
        if file_exists(path):
            return head_file(path)
        else:
            abort(404)


def head_file(path):
    file = S3File.from_s3path(path)
    head = '\n'.join(file.head())
    return render_template('head.html', head=head, path=file.path, filename=file.filename, 
        now=datetime.now())
    # make it look like the github page
    # show meta data: filename | 4.99 kb | last modified
    # https://github.com/boto/botocore/blob/develop/docs/make.bat

@app.template_filter()
def format_date(date):
    # return date.strftime('%d %b %Y %H:%M:%S')
    return date.strftime('%H:%M:%S')

@app.template_filter()
def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.

    http://flask.pocoo.org/snippets/33/
    """
    if not isinstance(dt, (datetime, date)):
        return dt
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    diff = now - dt
    
    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)
    return default