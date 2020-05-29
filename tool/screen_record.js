// Run this from the commandline:
// xvfb-run phantomjs lmgoogle.js | ffmpeg -y -c:v png -f image2pipe -r 24 -t 10  -i - -c:v libx264 -pix_fmt yuv420p -movflags +faststart output.mp4
// Thanks to: https://gist.github.com/phanan/e03f75082e6eb114a35c

var page = require('webpage').create(),
    address = 'https://url.com/link-here',
    duration = duration_taking, // duration of the video, in seconds
    framerate = 24, // number of frames per second. 24 is a good value.
    counter = 0,
    width = width_screen,
    height = height_screen;

page.viewportSize = { width: width, height: height };

page.open(address, function(status) {
    if (status !== 'success') {
        console.log('Unable to load the address!');
        phantom.exit(1);
    } else {
        window.setTimeout(function () {
            page.clipRect = { top: 0, left: 0, width: width, height: height };

            window.setInterval(function () {
                counter++;
                page.render('/dev/stdout', { format: 'png' });
                if (counter > duration * framerate) {
                    phantom.exit();
                }
            }, 1/framerate);
        }, 200);
    }
});