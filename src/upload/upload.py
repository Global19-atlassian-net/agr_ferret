# Functions for use in downloading files.

import logging, os, requests, json, hashlib, urllib
from requests_toolbelt.utils import dump
from retry import retry
from app import ContextInfo

logger = logging.getLogger(__name__)

def create_md5(worker, filename, save_path):
    # Generate md5
    logger.info('{}: Generating md5 hash for {}.'.format(worker, filename))
    hash_md5 = hashlib.md5()
    with open(save_path + '/' + filename, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    logger.info('{}: Finished generating md5 hash: {}'.format(worker, hash_md5.hexdigest()))

    return hash_md5.hexdigest()

def upload_file(worker, filename, save_path, upload_file_prefix, context_info):
    file_to_upload = {upload_file_prefix: open(save_path + "/" + filename, 'rb')}

    headers = {
        'Authorization': 'Bearer {}'.format(context_info.config['API_KEY'])
    }

    logger.debug('{}: Attempting upload of data file: {}'.format(worker, save_path + '/' + filename, ))
    logger.debug('{}: Attempting upload with header: {}'.format(worker, headers))
    logger.info("{}: Uploading data to {}) ...".format(worker, context_info.config['FMS_URL']))

    response = requests.post(context_info.config['FMS_URL'], files=file_to_upload, headers=headers)
    logger.info(response.text)

@retry(tries=5, delay=5, logger=logger)
def upload_process(worker, filename, save_path, data_type, data_sub_type):

    context_info = ContextInfo()

    schema = context_info.config['schema']
    upload_file_prefix = '{}_{}_{}'.format(schema, data_type, data_sub_type)

    generated_md5 = create_md5(worker, filename, save_path)

    # Attempt to grab MD5 for the latest version of the file.
    url_to_check = 'http://fmsdev.alliancegenome.org/api/datafile/{}/{}?latest=true'.format(data_type, data_sub_type)
    chip_response = urllib.request.urlopen(url_to_check)
    chip_data = data = json.loads(chip_response.read().decode(chip_response.info().get_param('charset') or 'utf-8'))
    logger.debug('{}: Retrieved API data from chipmunk: {}'.format(worker, chip_data))

    # Check for existing MD5
    logger.info('{}: Checking for existing MD5 from chipmunk.'.format(worker))

    # Logic for uploading new files based on existing and new MD5s.
    existing_md5 = chip_data[0].get('md5Sum')
    if existing_md5:
        logger.info('{}: Previous MD5 found: {}'.format(worker, existing_md5))
        if existing_md5 == generated_md5:
            logger.info('{}: Existing MD5 matches the newly generated MD5. The file will not be uploaded.'.format(worker))
            logger.info('{}: File: {}'.format(worker, filename))
            logger.info('{}: Existing: {} New: {}'.format(worker, existing_md5, generated_md5))
        else:
            logger.info('{}: Existing MD5 does not match the newly generated MD5. A new file will be uploaded.'.format(worker))
            logger.info('{}: File: {}'.format(worker, filename))
            logger.info('{}: Existing: {} New: {}'.format(worker, existing_md5, generated_md5))
            upload_file(worker, filename, save_path, upload_file_prefix, context_info)
    else:
        logger.info('{}: Existing MD5 not found. A new file will be uploaded.'.format(worker))
        logger.info('{}: File: {}'.format(worker, filename))
        logger.info('{}: Existing: {} New: {}'.format(worker, existing_md5, generated_md5))
        upload_file(worker, filename, save_path, upload_file_prefix, context_info)
