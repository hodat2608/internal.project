# built_in_mapping_mode = {'built-in-camera-1': {'modes': {'automatic_mode': 'Auto 1', 'mirror_mode': 'Auto 2', 'logging_mode': 'Auto 3'}}}
# print(built_in_mapping_mode['built-in-camera-1']['modes']['automatic_mode'])








# detections           xmin        ymin         xmax         ymax  confidence  class  \
# 0   602.493469  478.628723   951.800842  1133.484131    0.989803      3
# 1  1568.607178  471.846497  1927.765503  1146.963501    0.965890      3
# 2  1437.095947  881.444458  2058.440186  1113.431152    0.956838      5
# 3   914.232727  920.124695  1038.723267  1136.530151    0.947967      0

#         name
# 0  chan_comi
# 1  chan_comi
# 2     jumper
# 3   chay_day




# xywh_list [[772.17333984375, 809.3460083007812, 355.4842529296875, 658.2374267578125], [1754.1632080078125, 807.200927734375, 346.359619140625, 670.627685546875], [977.0526123046875, 1034.3798828125, 123.014892578125, 215.47918701171875], [1697.9705810546875, 989.922607421875, 644.278564453125, 222.314697265625]]
# cls_list [3.0, 3.0, 0.0, 5.0]
# conf_list [0.9677001237869263, 0.9486720561981201, 0.7170145511627197, 0.6256713271141052]
dict_processors = {('camera-1', 'model-1'): '<module_3.handle_option_models.Process_Model object at 0x00000208510350A0>', ('camera-1', 'model-2'): '<module_3.handle_option_models.Process_Model object at 0x000002084F8BE570>', ('camera-1', 'model-3'): '<module_3.handle_option_models.Process_Model object at 0x000002085F0A6C30>', ('camera-1', 'model-4'): '<module_3.handle_option_models.Process_Model object at 0x0000020851044FB0>', ('camera-1', 'model-5'): '<module_3.handle_option_models.Process_Model object at 0x000002085F1A3230>', ('camera-2', 'model-1'): '<module_3.handle_option_models.Process_Model object at 0x000002084F80C470>', ('camera-2', 'model-2'): '<module_3.handle_option_models.Process_Model object at 0x0000020864F00A70>', ('camera-2', 'model-3'): '<module_3.handle_option_models.Process_Model object at 0x0000020864F421B0>', ('camera-2', 'model-4'): '<module_3.handle_option_models.Process_Model object at 0x000002085F3275F0>', ('camera-3', 'model-1'): '<module_3.handle_option_models.Process_Model object at 0x0000020864EC5640>'}
print(dict_processors[('camera-1', 'model-1')])

list_mode ={   
    'automatic':
                    {
                    'mapping_mode' :'Auto 1',
                    'trigger_selected': 'trigger',
                    'component' : 'reset_ok',
                    'completed' : 'complete'
                    },

    'mirror':
                    {
                    'mapping_mode' :'Auto 2',
                    'trigger_selected': 'trigger',
                    'component' : 'None',
                    'completed' : 'complete'
                    },
    
    'logging':
                    {
                    'mapping_mode' :'Auto 3',
                    'trigger_selected': 'trigger',
                    'component' : 'None',
                    'completed' : 'None'
                    }
}



list_mode =  {'automatic': {'mapping_mode': 'Auto 1', 'trigger_selected': 'trigger', 'component': 'reset_ok', 'completed': 'complete'}, 'mirror': {'mapping_mode': 'Auto 2', 'trigger_selected': 'trigger', 'component': 'None', 'completed': 'complete'}, 'logging': {'mapping_mode': 'Auto 3', 'trigger_selected': 'trigger', 'component': 'None', 'completed': 'None'}}
automatic_mode = list_mode.get('automatic', {}).get('mapping_mode')
trigger_selected = list_mode.get('automatic', {}).get('trigger_selected')
component = list_mode.get('automatic', {}).get('component')
completed = list_mode.get('automatic', {}).get('completed')

print(automatic_mode)
print(trigger_selected)
print(component)
print(completed)    