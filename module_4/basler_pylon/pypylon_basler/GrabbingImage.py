'''
A simple Program for grabing video from basler camera and converting it to opencv img.
Tested on Basler acA1920-25uc (USB3, Window x64 , python 3.12)

'''
from pypylon import pylon
import cv2
import time
import numpy as np
devices = pylon.TlFactory.GetInstance().EnumerateDevices()
for d in devices:
    print(d.GetModelName(), d.GetSerialNumber(), d)
print(devices[0])
camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(devices[0]))
camera.Open()
camera.UserSetSelector.SetValue('Default')
camera.UserSetLoad.Execute()
camera.Width.SetValue(1722)
camera.Height.SetValue(960)

camera.OffsetX.SetValue(0)
camera.OffsetY.SetValue(0)

camera.ExposureTime.SetValue(camera.ExposureTime.GetValue())

camera.Gain.SetValue(camera.Gain.GetValue())

camera.AcquisitionFrameRate.SetValue(camera.AcquisitionFrameRate.GetValue())

camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
converter = pylon.ImageFormatConverter()

converter.OutputPixelFormat = pylon.PixelType_RGB16packed
converter.OutputBitAlignment = pylon.OutputBitAlignment_LsbAligned

# while camera.IsGrabbing():
startTime = time.time()
grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

if grabResult.GrabSucceeded():
    image = grabResult.GetArray()
    cv2.namedWindow('Video', cv2.WINDOW_AUTOSIZE)
    cv2.imshow('Video', image)
    cv2.imwrite('dat.jpg', image)
    k = cv2.waitKey(1)
    # if k == 27:
    #     break
grabResult.Release()

runningTime = (time.time() - startTime)
fps = 1.0/runningTime
print ("%f  FPS" % fps)

# Releasing the resource    
camera.StopGrabbing()
camera.DestroyDevice()
cv2.destroyAllWindows()