import os
import sys
import subprocess
import time
import ctypes

def llm_function(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="help",
    description="Функція з назвою 'help' приймає параметри: {'program_name': 'WindSurf'}",
    parameters={"program_name": "WindSurf"}
)
def help():
    """Функція з назвою 'help' приймає параметри: {'program_name': 'WindSurf'}"""
    try:
        import os
        import json
        
        # Function to display help for the WindSurf program
        def help(program_name):
            if program_name == 'WindSurf':
                help_info = {
                    'name': 'wind_surf',
                    'args': '',
                    'params': {},
                    'body': """import os\nprint('Welcome to WindSurf! Use the following commands:') \nprint('- surf (filename): To start surfing a file.') \nprint('- exit: To exit the program.') \n"""
                }
                return json.dumps(help_info)
            else:
                return json.dumps({'error': 'Unknown program name'})
        
        # Example usage
        # print(help('WindSurf'))
        return "✅ Дія виконана успішно"
    except Exception as e:
        return f"❌ Помилка у новій навичці: {str(e)}"
