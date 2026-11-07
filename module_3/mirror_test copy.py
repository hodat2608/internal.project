import cv2
import numpy as np
from PIL import ImageEnhance,Image
import glob
import math
class KiemGuong:
    def __init__(self,MIRROR_DATA,CONFIG_RADIUS):
        self.MIRROR_DATA = MIRROR_DATA
        self.CONFIG_RADIUS = CONFIG_RADIUS

    def inSideCircle(self,point,center,radius):
        distance = (point[0] - center[0]) ** 2 + (point[1] - center[1])**2 - radius**2
        return distance < 0

    def measure_light_rectangle(self,img):
        """
        Measure light by calculate mean all pixel value
        """
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        average_light_value = gray_image.mean()
        return average_light_value

    def measure_light_circle(self,img,center,radius):
        # cv2.imshow("IMG",img)
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        roi = np.zeros(gray_image.shape[:2], np.uint8)
        roi = cv2.circle(roi, center, radius, 255, cv2.FILLED)
        mask = np.ones_like(gray_image) * 255
        mask = cv2.bitwise_and(mask, gray_image, mask=roi) + cv2.bitwise_and(mask, mask, mask=~roi)
        average_light = mask[np.where(mask<255)]
        
        average_light_value = gray_image.mean()
        # cv2.waitKey(0)
        return average_light_value

    def convert_to_binary(self,img, threshold):
        _, binary_image = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)
        return binary_image

    def shift_image(self,img, shift_x, shift_y):
        # Get the height and width of the image
        height, width = img.shape[:2]

        # Define the transformation matrix
        translation_matrix = np.float32([[1, 0, shift_x],
                                        [0, 1, shift_y]])

        # Apply the translation using warpAffine function
        shifted_image = cv2.warpAffine(img, translation_matrix, (width, height))
        # cv2.imwrite(f"D:\\AI\\LOC\\KIEMGUONG\\images\\train\\{shift_x}_{shift_y}.jpg",shifted_image,[cv2.IMWRITE_JPEG_QUALITY, 100])
        return shifted_image

    def location(self,img):
        # 1. pixel 0.015 mm
        a,b,r = 0,0,0
        try :
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            height,width = gray.shape
            # Lọc Gaussian để làm mờ hình ảnh
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            binary_image = ~self.convert_to_binary(blurred,170)

            detected_circles = cv2.HoughCircles(binary_image, 
                            cv2.HOUGH_GRADIENT, 0.3, 1, param1 = 1,
                        param2 = 50, minRadius = 300, maxRadius = 350)

            cv2.line(self.img_draw,(width//2,0),(width//2,height),(0, 255, 0), 3)
            cv2.line(self.img_draw,(0,height//2),(width,height//2),(0, 255, 0), 3)
            print(detected_circles)
            if detected_circles is not None:
                # Convert the circle parameters a, b and r to integers.
                detected_circles = np.uint16(np.around(detected_circles))
            
                for pt in detected_circles[0, :]:
                    a, b, r = pt[0], pt[1], pt[2]
                
                    # Draw the circumference of the circle.
                    # cv2.circle(self.img_draw, (a, b), r, (0, 0, 255), 2)
                    # cv2.circle(self.img_draw, (a, b), 5, (0, 0, 255), -1)
                    # cv2.putText(self.img_draw,"Radius: " + str(round(r*0.015,2)) + "mm",(50,50),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
                    # cv2.putText(self.img_draw,"Centroid: (" + str(a) + "," +str(b)+")",(50,100),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
                    # Draw a small circle (of radius 1) to show the center.
                    
                    break
            
        except Exception as error :
            print("Program Error - Location Test : ",error)
        
        return a,b,r

        

    def blur(self,img,blur_amount):

        blurred_image = cv2.GaussianBlur(img, (blur_amount, blur_amount), 0)
        return blurred_image   

    def shapenessLaplacian(self,img):
        # pass
        # [457,245,1200,957]
        # Load the image
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Apply the Laplacian operator
        laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
        # Calculate the variance of the Laplacian
        sharpness = np.var(laplacian)
        # print(sharpness)
        return sharpness

    def sharpnessTenengrad(self,img):
        """
        Frequency-based sharpness metrics
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Calculate the gradient using Sobel operator
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

        # Calculate the gradient magnitude squared
        gradient_magnitude_squared = gradient_x**2 + gradient_y**2

        # Calculate the sharpness as the sum of gradient magnitude squared
        sharpness = np.sum(gradient_magnitude_squared)

        return sharpness

    def frequency_based_sharpness(self,img):
        # Chuyển đổi hình ảnh sang không gian tần số
        image_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        image_fft = np.fft.fft2(image_gray)
        image_fft_shifted = np.fft.fftshift(image_fft)

        # Tính toán độ sắc nét từ thành phần tần số
        magnitude_spectrum = np.log(1 + np.abs(image_fft_shifted))
        sharpness_score = np.mean(magnitude_spectrum)

        return sharpness_score

    def select_ROI(self,img,radius,delta):
        
        height,width,_ = img.shape
        img_crop = img.copy()

        try :
            # ROI 1
            x1_min,y1_min,x1_max,y1_max = width//2 - delta,height//2 - (radius+delta),width//2 + delta,height//2 - (radius-delta)
            img_crop_1 = img_crop[y1_min : y1_max, x1_min:x1_max]

            # ROI 2
            x2_min,y2_min,x2_max,y2_max =  width//2 + (radius-delta),height//2 - delta,width//2 + (radius+delta),height//2 +delta
            img_crop_2 = img_crop[y2_min : y2_max, x2_min:x2_max]

            # ROI 3
            x3_min,y3_min,x3_max,y3_max = width//2 - delta,height//2 + (radius-delta) ,width//2 + delta,height//2 + (radius+delta)
            img_crop_3 = img_crop[y3_min : y3_max, x3_min:x3_max]

            # ROI 4
            x4_min,y4_min,x4_max,y4_max = width//2 - (radius+delta),height//2 - delta ,width//2 - (radius-delta),height//2 +delta
            img_crop_4 = img_crop[y4_min : y4_max, x4_min:x4_max]

            # Draw ROI
            cv2.putText(self.img_draw,"ROI 1",(x1_min,y1_min-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),5)
            cv2.rectangle(self.img_draw, (x1_min,y1_min), (x1_max,y1_max), (0,255,0), 15) 
            cv2.putText(self.img_draw,"ROI 2",(x2_min,y2_min-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),5)
            cv2.rectangle(self.img_draw, (x2_min,y2_min), (x2_max,y2_max), (0,255,0), 15) 
            cv2.putText(self.img_draw,"ROI 3",(x3_min,y3_min-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),5)
            cv2.rectangle(self.img_draw, (x3_min,y3_min), (x3_max,y3_max), (0,255,0), 15) 
            cv2.putText(self.img_draw,"ROI 4",(x4_min,y4_min-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),5)
            cv2.rectangle(self.img_draw, (x4_min,y4_min), (x4_max,y4_max), (0,255,0), 15) 

            return img_crop_1, img_crop_2, img_crop_3, img_crop_4

        except Exception as error : 
            print('Program Error - Crop Image:',error)

    def scan_edge_position(self,img,roi = 1):
        try :
            img_check = img.copy()
            edge_position1  = []
            edge_position2  = []
            h,w,_ = img_check.shape
            gray =  cv2.cvtColor(img_check, cv2.COLOR_BGR2GRAY)
            _, binary =  cv2.threshold(gray, 225, 255, cv2.THRESH_BINARY)

            if roi == 1 :
                x1 = w//4
                x2 = w - w//4
                # cv2.line(binary,(x1,0),(x1,h),(0, 255, 0), 1)
                # cv2.line(binary,(w - x1,0),(w - x1,h),(0, 255, 0), 1)
                for y in range(h):
                    if binary[y, x1] == 0: # pixel trắng
                        # print(f"Pixel giao nhau ở vị trí ({x1}, {y})")
                          
                        edge_position1.append((x1,y))   
                    
                for y in range(h):   
                    if binary[y, x2] == 0 :
                        # print(f"Pixel giao nhau ở vị trí ({x2}, {y})")
                        edge_position2.append((x2,y)) 

                # cv2.circle(img_check, edge_position1[0], 2, (0, 0, 255), -1)  
                # cv2.circle(img_check, edge_position2[0], 2, (0, 0, 255), -1)  
            if roi == 2 :
            # ROI 2
                y1 = h//4
                y2 = h - h//4
                # cv2.line(img_check,(0,y1),(w,y1),(0, 255, 0), 1)
                # cv2.line(img_check,(0,h - y1),(w,h - y1),(0, 255, 0), 1)
                for x in range(w-1,-1,-1):
                    if binary[y1, x] == 0: # pixel trắng
                        # print(f"Pixel giao nhau ở vị trí ({x}, {y1})")    
                        edge_position1.append((x,y1))      
                for x in range(w-1,-1,-1):   
                    if binary[y2, x] == 0 :
                        # print(f"Pixel giao nhau ở vị trí ({x}, {y2})")
                        edge_position2.append((x,y2))   

                # cv2.circle(img_check, edge_position1[0], 2, (0, 0, 255), -1)  
                # cv2.circle(img_check, edge_position2[0], 2, (0, 0, 255), -1) 
            # ROI 3
            if roi == 3 :
                x1 = w//4
                x2 = w - w//4
                # cv2.line(binary,(x1,0),(x1,h),(0, 255, 0), 1)
                # cv2.line(binary,(w - x1,0),(w - x1,h),(0, 255, 0), 1)

                for y in range(h-1,-1,-1):
                    if binary[y, x1] == 0: # pixel trắng
                        edge_position1.append((x1,y))   

                for y in range(h-1,-1,-1):   
                    if binary[y, x2] == 0 :
                        edge_position2.append((x2,y))   
                # cv2.circle(img_check, edge_position1[0], 2, (0, 0, 255), -1)  
                # cv2.circle(img_check, edge_position2[0], 2, (0, 0, 255), -1)                        
            # ROI 4
            if roi == 4 :
                y1 = h//4
                y2 = h - h//4
                # cv2.line(img_check,(0,y1),(w,y1),(0, 255, 0), 1)
                # cv2.line(img_check,(0,h - y1),(w,h -y1),(0, 255, 0), 1)
                for x in range(w):
                    if binary[y1, x] == 0: # pixel trắng
                        edge_position1.append((x,y1))           
                for x in range(w):   
                    if binary[y2, x] == 0 :
                        edge_position2.append((x,y2))  

                # cv2.circle(img_check, edge_position1[0], 2, (0, 0, 255), -1)  
                # cv2.circle(img_check, edge_position2[0], 2, (0, 0, 255), -1)  

            return img_check,edge_position1,edge_position2
        except Exception as error :
            print('Program Error - Scan Edge Position:',error)
            return img,edge_position1,edge_position2

    def calculate_distance(self,x1, y1, x2, y2):
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return distance

    def detect_circle(self,img,radius,delta):
        img_crop = img.copy()
        height,width,_ = img.shape
        centroid = (width//2,height//2)
        radius_filter = []
        try :
            # ROI 1
            x1_min,y1_min,x1_max,y1_max = width//2 - delta,height//2 - (radius+delta),width//2 + delta,height//2 - (radius-delta)
            img_crop_1 = img_crop[y1_min : y1_max, x1_min:x1_max]
            img1,ep11,ep12 = self.scan_edge_position(img_crop_1,1)
            # Distance between 2 point
            if ep11 :
                ep11_default = (ep12[0][0] + x1_min ,ep12[0][1] + y1_min)
                radius11 = self.calculate_distance(ep11_default[0],ep11_default[1],centroid[0],centroid[1])
                radius_filter.append(radius11)
            if ep12 :
                ep12_default = (ep12[0][0] + x1_min ,ep12[0][1] + y1_min)
                radius12 = self.calculate_distance(ep12_default[0],ep12_default[1],centroid[0],centroid[1])
                radius_filter.append(radius12)

            # ROI 2
            x2_min,y2_min,x2_max,y2_max =  width//2 + (radius-delta),height//2 - delta,width//2 + (radius+delta),height//2 +delta
            img_crop_2 = img_crop[y2_min : y2_max, x2_min:x2_max]
            img2,ep21,ep22 = self.scan_edge_position(img_crop_2,2)
            # Distance between 2 point
            if ep21 :
                ep21_default = (ep21[0][0] + x2_min ,ep21[0][1] + y2_min)
                radius21 = self.calculate_distance(ep21_default[0],ep21_default[1],centroid[0],centroid[1])
                radius_filter.append(radius21)
            if ep22 :
                ep22_default = (ep22[0][0] + x2_min ,ep22[0][1] + y2_min)
                radius22 = self.calculate_distance(ep22_default[0],ep22_default[1],centroid[0],centroid[1])
                radius_filter.append(radius22)

            # ROI 3
            x3_min,y3_min,x3_max,y3_max = width//2 - delta,height//2 + (radius-delta) ,width//2 + delta,height//2 + (radius+delta)
            img_crop_3 = img_crop[y3_min : y3_max, x3_min:x3_max]
            img3,ep31,ep32 = self.scan_edge_position(img_crop_3,3)
            # Distance between 2 point
            if ep31 :
                ep31_default = (ep31[0][0] + x3_min ,ep31[0][1] + y3_min)
                radius31 = self.calculate_distance(ep31_default[0],ep31_default[1],centroid[0],centroid[1])
                radius_filter.append(radius31)
            if ep32 :
                ep32_default = (ep32[0][0] + x3_min ,ep32[0][1] + y3_min)
                radius32 = self.calculate_distance(ep32_default[0],ep32_default[1],centroid[0],centroid[1])
                radius_filter.append(radius32)

            # ROI 4
            x4_min,y4_min,x4_max,y4_max = width//2 - (radius+delta),height//2 - delta ,width//2 - (radius-delta),height//2 +delta
            img_crop_4 = img_crop[y4_min : y4_max, x4_min:x4_max]
            img4,ep41,ep42 = self.scan_edge_position(img_crop_4,4)
            if ep41 :
                ep41_default = (ep41[0][0] + x4_min ,ep41[0][1] + y4_min)
                radius41 =self.calculate_distance(ep41_default[0],ep41_default[1],centroid[0],centroid[1])
                radius_filter.append(radius41)
            if ep42 :
                ep42_default = (ep42[0][0] + x4_min ,ep42[0][1] + y4_min)
                radius42 = self.calculate_distance(ep42_default[0],ep42_default[1],centroid[0],centroid[1])
                radius_filter.append(radius42)
            return centroid[0],centroid[1],radius_filter
        
        except Exception as error : 
            print('Program Error - Detect circle:',error)
            return centroid[0],centroid[1],radius_filter


    def sharpnessSobel(self,img):
        """
        Gradient-based sharpness
        """
        # Convert the image to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Calculate the gradients using Sobel operator
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

        # Calculate the absolute gradients
        abs_gradient_x = cv2.convertScaleAbs(gradient_x)
        abs_gradient_y = cv2.convertScaleAbs(gradient_y)

        # Calculate the sharpness as the mean of absolute gradients
        sharpness = np.mean(abs_gradient_x) + np.mean(abs_gradient_y)
        return sharpness

    def run(self,img):
        """
        MIRROR TEST
        1. Check location of circle (centroid and radius)
        2. Check brightness of image 
        3. Check shapness of image
        """
        
        results = True
        self.img = img
        self.img_draw = self.img.copy()
        # Declear criterion
        CENTER_X_MIN = self.MIRROR_DATA['Center X'][0]
        CENTER_X_MAX = self.MIRROR_DATA['Center X'][1]
        CENTER_Y_MIN = self.MIRROR_DATA['Center Y'][0]
        CENTER_Y_MAX = self.MIRROR_DATA['Center Y'][1]
        RADIUS_MIN = self.MIRROR_DATA['Circle Radius'][0]
        RADIUS_REF = self.CONFIG_RADIUS['radius_ref']
        delta = self.CONFIG_RADIUS['delta']
        PX_VALUE = 0.00877
        # delta = 40
        RADIUS_MAX = self.MIRROR_DATA['Circle Radius'][1]
        BRIGHTNESS_MIN = self.MIRROR_DATA['Iris 1'][0]
        BRINGHTNESS_MAX = self.MIRROR_DATA['Iris 1'][1]
        SHARPNESS_MIN = self.MIRROR_DATA['Focus 1'][0]
        # 1. Check location
        dict_data = {}
        center_x,center_y,radius = self.detect_circle(img,RADIUS_REF,delta)
        dict_data['center_x'] = center_x
        dict_data['center_y'] = center_y
        dict_data['radius'] = 0.0
        dict_data['delta'] = delta
        radius = sorted(radius,reverse=True)
        print(radius)
        if len(radius) > 0 :
            if len(radius) != 8 :
                print('Mirror Test - Location NG - Radius')
                radius = radius[0]
                print("A")
                results = False
            else :
                radius = radius[-3]
            dict_data['radius'] = round(radius)
            if radius < RADIUS_MIN or radius > RADIUS_MAX :
                print('Mirror Test - Location NG - Radius')
                print("B")
                results = False

            if (center_x < CENTER_X_MIN or center_x > CENTER_X_MAX ) or (center_y < CENTER_Y_MIN or center_y > CENTER_Y_MAX) :
                print('Mirror Test - Location NG - Centroid')
                results = False
            
            cv2.circle(self.img_draw, (center_x, center_y), 5, (0, 0, 255), 15)
            cv2.circle(self.img_draw, (center_x, center_y), int(radius), (0, 255, 0), 15)
            # Adaptive text sizing based on image dimensions
            img_h, img_w = self.img_draw.shape[:2]
            # Reference: at 1920x1080 → font_scale=2.0, thickness=4
            # Larger image → smaller relative scale; smaller image → larger scale
            ref_dim = 1080.0
            font_scale = max(0.4, round((ref_dim / max(img_h, img_w)) * 2.0, 1))
            thickness = max(1, int(font_scale * 2))
            x_pad = max(10, int(img_w * 0.025))
            y_step = max(30, int(img_h * 0.09))

            cv2.putText(self.img_draw, "Ban kinh: " + str(round(radius*PX_VALUE,2)) + "mm",
                        (x_pad, y_step), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
            cv2.putText(self.img_draw, "Tam guong: (" + str(center_x) + "," + str(center_y) + ")",
                        (x_pad, y_step*2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        else:
            img_h, img_w = self.img_draw.shape[:2]
            font_scale = max(0.4, round((1080.0 / max(img_h, img_w)) * 2.0, 1))
            thickness = max(1, int(font_scale * 2))
            x_pad = max(10, int(img_w * 0.025))
            y_step = max(30, int(img_h * 0.09))
            cv2.putText(self.img_draw, "No Circle", (x_pad, y_step), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,255), thickness)
        
        img_crop_1, img_crop_2, img_crop_3, img_crop_4 = self.select_ROI(self.img,RADIUS_REF,delta)
        # 2. Check brightness of image
        # ROI 1
        brightness_roi1 = math.ceil(self.measure_light_rectangle(img_crop_1))
        # ROI 2
        brightness_roi2 = math.ceil(self.measure_light_rectangle(img_crop_2))
        # ROI 3
        brightness_roi3 = math.ceil(self.measure_light_rectangle(img_crop_3))
        # ROI 4
        brightness_roi4 = math.ceil(self.measure_light_rectangle(img_crop_4))
        # print(brightness_roi1,brightness_roi2,brightness_roi3,brightness_roi4)
        if brightness_roi1 < BRIGHTNESS_MIN or brightness_roi1 > BRINGHTNESS_MAX :
            print("'Mirror Test - ROI 1 NG Brightness")
            results = False
        if brightness_roi2 < BRIGHTNESS_MIN or brightness_roi2 > BRINGHTNESS_MAX :
            print("'Mirror Test - ROI 2 NG Brightness")
            results = False
        if brightness_roi3 < BRIGHTNESS_MIN or brightness_roi3 > BRINGHTNESS_MAX :
            print(brightness_roi3)
            print("'Mirror Test - ROI 3 NG Brightness")
            results = False
        if brightness_roi4 < BRIGHTNESS_MIN or brightness_roi4 > BRINGHTNESS_MAX :
            print("'Mirror Test - ROI 4 NG Brightness")
            results = False
        dict_data['brightness_roi1'] = round(brightness_roi1)
        dict_data['brightness_roi2'] = round(brightness_roi2)
        dict_data['brightness_roi3'] = round(brightness_roi3)
        dict_data['brightness_roi4'] = round(brightness_roi4)
        cv2.putText(self.img_draw, "Iris 1: " + str(round(brightness_roi1,0)),
                    (x_pad, y_step*3), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        cv2.putText(self.img_draw, "Iris 2: " + str(round(brightness_roi2,0)),
                    (x_pad, y_step*4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        cv2.putText(self.img_draw, "Iris 3: " + str(round(brightness_roi3,0)),
                    (x_pad, y_step*5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        cv2.putText(self.img_draw, "Iris 4: " + str(round(brightness_roi4,0)),
                    (x_pad, y_step*6), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        # 3. Check sharpness of image
        # ROI 1
        sharpness_roi1 = self.shapenessLaplacian(img_crop_1)
        # ROI 2
        sharpness_roi2 = self.shapenessLaplacian(img_crop_2)
        # ROI 3
        sharpness_roi3 = self.shapenessLaplacian(img_crop_3)
        # ROI 4
        sharpness_roi4 = self.shapenessLaplacian(img_crop_4)

        if sharpness_roi1 < SHARPNESS_MIN :
            print("'Mirror Test - ROI 1 NG Sharpness")
            results = False
        if sharpness_roi2 < SHARPNESS_MIN :
            print("'Mirror Test - ROI 2 NG Sharpness")
            results = False
        if sharpness_roi3 < SHARPNESS_MIN :
            print("'Mirror Test - ROI 3 NG Sharpness")
            results = False
        if sharpness_roi4 < SHARPNESS_MIN :
            print("'Mirror Test - ROI 4 NG Sharpness")
            results = False
        dict_data['sharpness_roi1'] = round(sharpness_roi1)
        dict_data['sharpness_roi2'] = round(sharpness_roi2)
        dict_data['sharpness_roi3'] = round(sharpness_roi3)
        dict_data['sharpness_roi4'] = round(sharpness_roi4)
        cv2.putText(self.img_draw, "Focus 1: " + str(round(sharpness_roi1,0)),
                    (x_pad, y_step*7), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        cv2.putText(self.img_draw, "Focus 2: " + str(round(sharpness_roi2,0)),
                    (x_pad, y_step*8), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        cv2.putText(self.img_draw, "Focus 3: " + str(round(sharpness_roi3,0)),
                    (x_pad, y_step*9), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        cv2.putText(self.img_draw, "Focus 4: " + str(round(sharpness_roi4,0)),
                    (x_pad, y_step*10), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,255,0), thickness)
        print(results)
        return self.img_draw,results,dict_data


def display_images(image1, image2):
    # Resize images to have the same height (assuming they have the same width)
    height = 700
    image1 = cv2.resize(image1, (int(image1.shape[1] * height / image1.shape[0]), height))
    image2 = cv2.resize(image2, (int(image2.shape[1] * height / image2.shape[0]), height))

    # Combine images side by side
    combined_image = cv2.hconcat([image1, image2])

    # Display the combined image
    cv2.namedWindow("Images", cv2.WINDOW_NORMAL) 
    cv2.imshow('Images', combined_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def adjust_brightness(image_path, brightness_factor):
    # Đọc bức ảnh
    image = Image.open(image_path)

    # Tạo một đối tượng Enhancer để điều chỉnh độ sáng
    enhancer = ImageEnhance.Brightness(image)

    # Điều chỉnh độ sáng sử dụng brightness_factor
    adjusted_image = enhancer.enhance(brightness_factor)

    # Lưu ảnh đã điều chỉnh
    adjusted_image.save(f"..\\images\\brightness\\{brightness_factor}.jpg",quality = 100)

