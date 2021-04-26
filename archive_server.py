import requests
import string
import random
import threading
from io import BytesIO
from zipfile import ZipFile
from flask import Flask, request, jsonify, redirect, Response
from werkzeug.wsgi import FileWrapper


app = Flask(__name__)
zip_collection_dict = {}    # dictionary which contain all archive objects, its ids and current status


@app.route('/api/archive/create', methods=['POST'])
def create_zip_endpoint():
    """
    Function which create archive file from provided URLs
    in separate thread and return it's
    :return: zip file id
    """

    received_urls = request.form.getlist('urls')
    zip_id = generate_zip_id(32)
    zip_collection_dict[zip_id] = {'status': 'in-progress'}
    zip_create_thread = threading.Thread(target=create_zip, kwargs={'zip_id': zip_id, 'urls': received_urls})
    zip_create_thread.start()
    return jsonify({'archive_hash': zip_id})


@app.route('/api/archive/status', methods=['POST'])
def check_status_endpoint():
    """
    Function which check generated archive status ny providing its id
    :return: redirect to generative subsite which will return status
    """

    zip_id = request.form('archive_hash')
    redirected_address = ('/api/archive/status/%s' % zip_id)
    return redirect(redirected_address)


@app.route('/api/archive/status/<redirected_address>')
def check_status(redirected_address):
    """
    Get archive status by its id
    :param redirected_address: represent archive id
    :return: archive status
    """

    zip_id = redirected_address
    if zip_id in zip_collection_dict.keys():
        status = zip_collection_dict[zip_id]['status']
        if status == 'completed':
            status = {
                'status': 'completed',
                'url': 'http://localhost:5000/archive/get/%s.zip' % zip_id
            }
        else:
            status = {'status': 'in-progress'}
    else:
        status = None
    return jsonify(status)


@app.route('/archive/get/<redirected_address>', methods=['GET'])
def download_zip_file(redirected_address):
    """
    download archive by id, if request includes range header,
    it will return file part started from byte which is provided by header
    :param redirected_address: represent archive id
    :return: :return: download response
    """

    zip_name = redirected_address
    zip_id = zip_name.split('.')[0]
    zip_buffered_archive = zip_collection_dict[zip_id]['archive']
    zip_io = BytesIO(zip_buffered_archive)
    file_wrapper = FileWrapper(zip_io)
    if request.range:
        range = request.range
        response = continue_downloading(zip_name, file_wrapper, range)
    else:
        response = new_downloading(zip_name, file_wrapper)
    return response


def continue_downloading(zip_name, file_wrapper, range):
    """
    Continue downloading if range header provided
    :param zip_name: archive name
    :param file_wrapper: object with archive
    :param range: byte from which script should continue downloading
    :return: download response
    """

    headers = {
        'Content-Disposition': 'attachment,'
        'filename=%s' % zip_name,
        'Status': '206',
        'Accept-Ranges':'bytes',
    }
    file_part = get_file_part(file_wrapper,range)
    response = Response(
        file_part,
        mimetype="application/zip",
        direct_passthrough=True,
        headers=headers
    )
    return response


def get_file_part(file_wrapper,range):
    """
    Get part of file started from provided byte
    :param file_wrapper: object with archive
    :param range: byte from which script should start
    :return: FileWrapper object with archive
    """
    start_byte = range.ranges[0][0]
    file_wrapper.seek(start_byte)
    return file_wrapper


def new_downloading(zip_name, file_wrapper):
    """
    Create response for downloading archive file
    :param zip_name: archive name
    :param file_wrapper: object with archive
    :return: download response
    """
    file_wrapper.seek(0)
    headers = {
        'Content-Disposition': 'attachment; filename=%s' % zip_name
    }
    response = Response(
        file_wrapper,
        mimetype="application/zip",
        direct_passthrough=True,
        headers=headers
    )
    return response


def generate_zip_id(length):
    """
    Generate random alphanumeric string
    :param length: integer variable with string length
    :return: alphanumeric string which will be used as archive id
    """
    chars = string.ascii_lowercase + string.digits + '-'
    zip_id = ''.join(random.choice(chars) for i in range(length))
    return zip_id


def create_zip(**kwargs):
    """
    Function starting create zip archive from provided urls,
    and send request to webhook after archive file is created
    :param kwargs: list of urls which will be used to generate zip file
    """
    received_urls = kwargs['urls']
    zip_id = kwargs['zip_id']
    create_zip_from_urls(received_urls, zip_id)
    requests.post('http://localhost:8000/webhook', json={"zip_id": zip_id})


def create_zip_from_urls(urls, zip_id):
    """
    Create archive file with provided provided urls list
    and put it into zip_collection_dict dictionary
    :param urls: list of urls to archive
    :param zip_id: id of this archive file
    :return: True
    """
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        for url in urls:
            file_name = get_url_file_name(url)
            file_as_bytes = get_url_as_bytes(url)
            zip_file.writestr(file_name, file_as_bytes)
    zip_collection_dict[zip_id]['archive'] = zip_buffer.getvalue()
    zip_buffer.close()
    zip_collection_dict[zip_id]['status'] = 'completed'
    return True


def get_url_file_name(url):
    """
    Get file name from url
    :param url: url of file
    :return: string with file name
    """
    url_head = requests.head(url)
    url_header_dict = url_head.headers   # dict with http headers
    if 'Location' in url_header_dict.keys():
        url = url_header_dict['Location']
    file_name = url.split('/')[-1]
    return file_name


def get_url_as_bytes(url):
    """
    Get file from url as bytes object
    :param url: file url
    :return: file as bytes
    """
    file = requests.get(url, allow_redirects=True)
    file_as_binary_stream = BytesIO(file.content)
    file_as_bytes = file_as_binary_stream.read()
    return file_as_bytes


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)