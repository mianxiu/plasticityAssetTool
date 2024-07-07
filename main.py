
import webview


def custom_logic(window):
    #window.toggle_fullscreen()
    window.evaluate_js('alert("Nice one brother")')

window = webview.create_window('Woah dude!', "plasticity-asset-tool-app/dist/index.html")
webview.start(custom_logic, window,http_port="15150")
# anything below this line will be executed after program is finished executing
pass


# from bottle import Bottle, run, static_file

# app = Bottle()

# @app.route('/')
# def index():
#     return static_file('index.html', root='dist/')

# if __name__ == '__main__':
#     run(app, host='localhost', port=8000)