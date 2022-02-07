### Installation
Tested on python version 3.7
To install all required packages type in the command line:
```
pip install -r requirements.txt
```
### Quick reference
The viewer is a set of two scripts: renderer.py and response_grabber.py  
***response_grabber.py*** - gets localization results from folder with query images  
```buildoutcfg
usage: response_grabber.py [-h] [--reference_images REFERENCE_IMAGES] [--hint HINT] [--use_oscp] directory

Grab images from selected directory and localize them

positional arguments:
  directory             Directory with images

optional arguments:
  -h, --help            show this help message and exit
  --reference_images REFERENCE_IMAGES
                        Directory with reference images
  --hint HINT           Series id to localized in
  --use_oscp            Use oscp api to localize

```
***renderer.py*** - render localization results in points cloud
```text
usage: renderer.py [-h] [--cs {local,enu,ecef}] [--no_filter] [--hide_objects] [--hide_cameras] [--hide_cloud] [--hide_frame] directory

Draw points cloud with cameras and placeholder

positional arguments:
  directory             Directory with points cloud and localization responses

optional arguments:
  -h, --help            show this help message and exit
  --cs {local,enu,ecef}
                        Show the result in a specified coordinate system
  --no_filter           Do not filter cloud
  --hide_objects        Hide objects
  --hide_cameras        Hide cameras
  --hide_cloud          Hide cloud
  --hide_frame          Hide cloud frame

```
### Step by step guide (The basic case)
1) Type in the command line:
```bash
python response_grabber.py c:\folder_with_images\
```

or in unix-like format:

```bash
python response_grabber.py /home/my_name/folder_with_images/
```
Where folder_with_images - the folder where image files for localization are located

2) After ***response_grabber.py*** will finish its work, A new folder will appear in the script folder - "responses".
The folder "responses" contains subfolders with timestamps of localizations. Every subfolder contains another subfolder  
with reconstruction id.  
   Example:
```text
responses/2021_02_19_18_20_02045025/14982
responses/2021_02_19_18_20_02045025/14985
responses/2021_02_19_18_20_02045025/15431
```
3) To render points cloud with localization results you need to type in command line:
```
python renderer.py responses/2021_02_19_18_20_02045025/14984/
```