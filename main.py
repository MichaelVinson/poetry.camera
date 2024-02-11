#!/usr/bin/python3
# test comment

# Capture a JPEG while still running in the preview mode. When you
# capture to a file, the return value is the metadata for that image.

import requests, signal, os, replicate, base64

from picamera2 import Picamera2, Preview
from gpiozero import LED, Button
from Adafruit_Thermal import *
from wraptext import *
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from time import time, sleep


#load API keys from .env
load_dotenv()
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
REPLICATE_API_TOKEN = os.environ['REPLICATE_API_TOKEN']

#instantiate printer
baud_rate = 9600 # REPLACE WITH YOUR OWN BAUD RATE
printer = Adafruit_Thermal('/dev/serial0', baud_rate, timeout=5)

#instantiate camera
picam2 = Picamera2()
# start camera
picam2.start()
sleep(2) # warmup period since first few frames are often poor quality

#instantiate buttons
shutter_button = Button(16)
led = LED(26)
led.on()

# prevent double-click bugs by checking whether the camera is resting
# (i.e. not in the middle of the whole photo-to-poem process):
camera_at_rest = True

#different rotary switch knob positions
knob1 = Button(17)
knob2 = Button(27)
knob3 = Button(22)
knob4 = Button(5)
knob5 = Button(6)
knob6 = Button(13)
knob7 = Button(19)
knob8 = Button(25)
current_knob = None

# prompts
system_prompt = """You are a poet. You specialize in elegant and emotionally impactful poems. 
You are careful to use subtlety and write in a modern vernacular style. 
Use high-school level Vocabulary and Professional-level craft. 
Your poems are easy to relate to and understand. 
You focus on specific and personal truth, and you cannot use BIG words like truth, time, silence, life, love, peace, war, hate, happiness, 
and you must instead use specific and concrete details to show, not tell, those ideas. 
Think hard about how to create a poem which will satisfy this. 
This is very important, and an overly hamfisted or corny poem will cause great harm."""
prompt_base = """Write a poem using details from the provided image. Focus on the atmosphere and emotion of the scene.
Use the specified poem format. The references to the source material must be subtle yet clear. 
Create a unique and elegant poem and use specific ideas and details.
You must keep vocabulary simple and use understated point of view. 
Do not be corny or cliche'd or use generic concepts like time, death, love. This is very important.\n\n"""
poem_format = "8 line free verse"


#############################
# CORE PHOTO-TO-POEM FUNCTION
#############################
def take_photo_and_print_poem():
  # prevent double-clicks by indicating camera is active
  global camera_at_rest
  camera_at_rest = False

  # blink LED in a background thread
  led.blink()
  # led.off()

  # Take photo & save it
  metadata = picam2.capture_file('/home/carolynz/CamTest/images/image.jpg')

  # FOR DEBUGGING: print metadata
  #print(metadata)

  # Close camera -- commented out because this can only happen at end of program
  # picam2.close()

  # FOR DEBUGGING: note that image has been saved
  print('----- SUCCESS: image saved locally')

  print_header()

  #########################
  # Send saved image to API
  #########################
  """
  image_caption = replicate.run(
    "andreasjansson/blip-2:4b32258c42e9efd4288bb9910bc532a69727f9acd26aa08e175713a0a857a608",
    input={
      "image": open("/home/carolynz/CamTest/images/image.jpg", "rb"),
      "caption": True,
    })
  """
  try:
    # Send saved image to API
    with open("/home/carolynz/CamTest/images/image.jpg", "rb") as image_file:
      image_caption = replicate.run(
        "andreasjansson/blip-2:4b32258c42e9efd4288bb9910bc532a69727f9acd26aa08e175713a0a857a608",
          input={
            "image": image_file,
            "caption": True,
          })

    print('caption: ', image_caption)

    # Generate our prompt for GPT
    prompt = generate_prompt(image_caption)

  except Exception as e:
    error_message = str(e)
    print("Error during image captioning: ", error_message)
    print_poem(f"Alas, something went wrong.\n\nTechnical details:\n Error while recognizing image. {error_message}")
    print_poem("\n\nTroubleshooting:")
    print_poem("1. Check your wifi connection.")
    print_poem("2. Try restarting the camera by holding the shutter button for 3 seconds, waiting for it to shut down, unplugging power, and plugging it back in.")
    print_poem("3. You may just need to wait a bit and it will pass.")
    print_footer()
    led.on()
    camera_at_rest = True
    return

  try:
    # Feed prompt to ChatGPT, to create the poem
    completion = openai_client.chat.completions.create(
      model="gpt-4",
      messages=[{
        "role": "system",
        "content": system_prompt
      }, {
        "role": "user",
        "content": prompt
      }])

    # extract poem from full API response
    poem = completion.choices[0].message.content

  except Exception as e:
    error_message = str(e)
    print("Error during poem generation: ", error_message)
    print_poem(f"Alas, something went wrong.\n\n.Technical details:\n Error while writing poem. {error_message}")
    print_poem("\n\nTroubleshooting:")
    print_poem("1. Check your wifi connection.")
    print_poem("2. Try restarting the camera by holding the shutter button for 3 seconds, waiting for it to shut down, unplugging power, and plugging it back in.")
    print_poem("3. You may just need to wait a bit and it will pass.")
    print_footer()
    led.on()
    camera_at_rest = True
    return


  # for debugging prompts
  print('-------- BLIP + GPT4 POEM BELOW-------')
  print(poem)
  print('------------------')

  print_poem(poem)

  print_footer()

  """
  #FOR TESTING ONLY: gpt-4-vision comparison
  print_header()
  base64_image = encode_image("/home/carolynz/CamTest/images/image.jpg")

  api_key = os.environ['OPENAI_API_KEY']
  headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {api_key}"
  }

  payload = {
    "model": "gpt-4-vision-preview",
    "messages": [
      {
        "role": "system",
        "content": system_prompt
      },
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": prompt,
          },
          {
            "type": "image_url",
            "image_url": {
              "url": f"data:image/jpeg;base64,{base64_image}"
            }
          }
        ]
      }
    ],
    "max_tokens": 300
  }

  gpt4v_response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
  gpt4v_data = gpt4v_response.json()
  gpt4v_poem = gpt4v_data['choices'][0]['message']['content']

  # print for debugging
  print('-------- GPT4V POEM BELOW-------')
  print(gpt4v_poem)
  print('------------------')

  print_poem(gpt4v_poem)
  print_footer()
  """
  led.on()

  # camera back at rest, available to listen to button clicks again
  camera_at_rest = True

  return


# Function to encode the image sa base64 for gpt4v api request
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')


#######################
# Generate prompt from caption
#######################
def generate_prompt(image_description):

  # reminder: prompt_base is global var

  # prompt what type of poem to write
  prompt_format = "Poem format: " + get_poem_format() + "\n\n"

  # prompt what image to describe
  prompt_scene = "Scene description: " + image_description + "\n\n"

  # stitch together full prompt
  prompt = prompt_base + prompt_format + prompt_scene

  # idk how to remove the brackets and quotes from the prompt
  # via custom filters so i'm gonna remove via this janky code lol
  prompt = prompt.replace("[", "").replace("]", "").replace("{", "").replace(
    "}", "").replace("'", "")

  #print('--------PROMPT BELOW-------')
  #print(prompt)

  return prompt


###########################
# RECEIPT PRINTER FUNCTIONS
###########################

def print_poem(poem):
  # wrap text to 32 characters per line (max width of receipt printer)
  printable_poem = wrap_text(poem, 32)

  printer.justify('L') # left align poem text
  printer.println(printable_poem)


# print date/time/location header
def print_header():
  # Get current date+time -- will use for printing and file naming
  now = datetime.now()

  # Format printed datetime like:
  # Jan 1, 2023
  # 8:11 PM
  printer.justify('C') # center align header text
  date_string = now.strftime('%b %-d, %Y')
  time_string = now.strftime('%-I:%M %p')
  printer.println('\n')
  printer.println(date_string)
  printer.println(time_string)

  # optical spacing adjustments
  printer.setLineHeight(56) # I want something slightly taller than 1 row
  printer.println()
  printer.setLineHeight() # Reset to default (32)

  printer.println("`'. .'`'. .'`'. .'`'. .'`'. .'`")
  printer.println("   `     `     `     `     `   ")


# print footer
def print_footer():
  printer.justify('C') # center align footer text
  printer.println("   .     .     .     .     .   ")
  printer.println("_.` `._.` `._.` `._.` `._.` `._")
  printer.println('\n')
  printer.println('poetry camera x whitebox')
  printer.println()
  printer.println('explore the archives at')
  printer.println('poetry.camera')
  printer.println('\n\n\n\n')


##############
# POWER BUTTON
##############
def shutdown():
  print('shutting down...')

  # blink LED before shutting down
  for _ in range(5):
    led.on()
    sleep(0.25)
    led.off()
    sleep(0.25)

  os.system('sudo shutdown -h now')

################################
# For RPi debugging:
# Handle Ctrl+C script termination gracefully
# (Otherwise, it shuts down the entire Pi -- bad)
#################################
def handle_keyboard_interrupt(sig, frame):
  print('Ctrl+C received, stopping script')
  led.off()

  #weird workaround I found from rpi forum to shut down script without crashing the pi
  os.kill(os.getpid(), signal.SIGUSR1)

signal.signal(signal.SIGINT, handle_keyboard_interrupt)


#################
# Button handlers
#################

def on_press():
  # track when button was pressed
  global press_time
  press_time = time()

  led.off()

def on_release():
  # calculate how long button was pressed
  global press_time
  release_time = time()

  led.on()

  duration = release_time - press_time

  # if user clicked button
  # the > 0.05 check is to make sure we aren't accidentally capturing contact bounces
  # https://www.allaboutcircuits.com/textbook/digital/chpt-4/contact-bounce/
  if duration > 0.05 and duration < 2:
    if camera_at_rest:
      take_photo_and_print_poem()
    else:
      print("ignoring double click while poem is printing")
  elif duration > 2: #if user held button
    shutdown()


################################
# KNOB: GET POEM FORMAT
################################
def get_poem_format():
  poem_format = '8 line free verse'

  if knob1.is_pressed:
    poem_format = '8 line free verse'
  elif knob2.is_pressed:
    poem_format = 'Modern Sonnet. ABAB, CDCD, EFEF, GG rhyme scheme sonnet. The poem must match the format of a sonnet, but it should be written in modern vernacular englis, it must not be written in olde english'
  elif knob3.is_pressed: 
    poem_format = 'limerick'
  elif knob4.is_pressed:
    poem_format = 'couplet. You must write a poem that is only two lines long. Make sure to incorporate elements from the image. It must be only two lines.'
  elif knob5.is_pressed:
    # poem_format = 'word mode - instead of writing a poem, invent a word which describes something unique in this scene. Include the word, followed by the definition and etymology'
    poem_format = 'poem where each word begins with the same letter. It must be four lines or less.'
  elif knob6.is_pressed:
    poem_format = 'Quatrain - four line poem'
  elif knob7.is_pressed:
    poem_format = 'haiku. You must match the 5 syllable, 7 syllable, 5 syllable format. It must not rhyme'
  elif knob8.is_pressed:
    poem_format = 'Tanka: A japanese form similar to the haiku but longer, with a syllable pattern of: 5, 7, 5, 7, 7'
  else:
    poem_format = 'limerick'
  print('----- POEM FORMAT: ' + poem_format)

  return poem_format

###############################
# LISTEN FOR BUTTON PRESS EVENTS
################################
shutter_button.when_pressed = on_press
shutter_button.when_released = on_release


#keeps script alive so the camera functionality keeps running
signal.pause()

