from flask import Flask, request

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def data_received():
    """
    waiting for request from archive_server
    :return: nothing
    """
    data = request.get_json()
    print('ZIP file with id %s is ready to download' % data['zip_id'])
    return ''


if __name__ == '__main__':
    app.run(debug=False, host='localhost', port=8000)
