/* rophako cms
   -----------
   HTML5 multi-upload script for the photo albums.
*/

function RophakoUpload() {
    var self = this;

    // Constants
    this.MAX_UPLOAD_FILE_SIZE = 1024*1024; // 1 MB
    this.UPLOAD_URL = "/photos/upload";
    this.NEXT_URL   = "/files/";

    // List of pending files to handle when the Upload button is finally clicked.
    this.PENDING_FILES  = [];

    this.ready = function() {
        // Set up the drag/drop zone.
        self.initDropbox();

        // Set up the handler for the file input box.
        $("#file-picker").on("change", function() {
            self.handleFiles(this.files);
        });

        // Handle the submit button.
        $("#upload-button").on("click", function(e) {
            // If the user has JS disabled, none of this code is running but the
            // file multi-upload input box should still work. In this case they'll
            // just POST to the upload endpoint directly. However, with JS we'll do
            // the POST using ajax and then redirect them ourself when done.
            e.preventDefault();
            self.doUpload();
        });
    };

    this.doUpload = function() {
        $("#upload-progress").show();
        var $progressBar   = $("#upload-progress-bar");

        // Gray out the form.
        $("#upload-button").attr("disabled", "disabled");

        // Initialize the progress bar.
        $progressBar.css({"width": "0%"});

        // Collect the form data.
        fd = self.collectFormData();

        // Attach the files.
        for (var i = 0, ie = self.PENDING_FILES.length; i < ie; i++) {
            // Collect the other form data.
            fd.append("file", self.PENDING_FILES[i]);
        }

        // Inform the back-end that we're doing this over ajax.
        fd.append("__ajax", "true");

        var xhr = $.ajax({
            xhr: function() {
                var xhrobj = $.ajaxSettings.xhr();
                if (xhrobj.upload) {
                    xhrobj.upload.addEventListener("progress", function(event) {
                        var percent = 0;
                        var position = event.loaded || event.position;
                        var total    = event.total;
                        if (event.lengthComputable) {
                            percent = Math.ceil(position / total * 100);
                        }

                        // Set the progress bar.
                        $progressBar.css({"width": percent + "%"});
                        $progressBar.text(percent + "%");
                    }, false)
                }
                return xhrobj;
            },
            url: self.UPLOAD_URL,
            method: "POST",
            contentType: false, //"multipart/form-data",
            processData: false,
            dataType: "json",
            cache: false,
            data: fd,
            success: function(data) {
                console.log(data);
                $progressBar.css({"width": "100%"});

                // How'd it go?
                if (data.status === "error") {
                    // Uh-oh.
                    window.alert(data.msg);
                    $("#upload-button").removeAttr("disabled");
                    return;
                }
                else {
                    // Ok!
                    window.location = data.msg;
                }
            },
        });
    };


    this.collectFormData = function() {
        // Go through all the form fields and collect their names/values.
        var fd = new FormData();

        $("#upload-form :input").each(function() {
            var $this = $(this);
            var name  = $this.attr("name");
            var type  = $this.attr("type") || "";
            var value = $this.val();

            // No name = no care.
            if (name === undefined) {
                return;
            }

            // Skip the file upload box for now.
            if (type === "file") {
                return;
            }

            // Checkboxes? Only add their value if they're checked.
            if (type === "checkbox" || type === "radio") {
                if (!$this.is(":checked")) {
                    return;
                }
            }

            fd.append(name, value);
        });

        return fd;
    };


    this.handleFiles = function(files) {
        // Add them to the pending files list.
        for (var i = 0, ie = files.length; i < ie; i++) {
            self.PENDING_FILES.push(files[i]);
        }
    };


    this.initDropbox = function() {
        var $dropbox = $("#dropbox");

        // On drag enter...
        $dropbox.on("dragenter", function(e) {
            e.stopPropagation();
            e.preventDefault();
            $(this).addClass("active");
        });

        // On drag over...
        $dropbox.on("dragover", function(e) {
            e.stopPropagation();
            e.preventDefault();
        });

        // On drop...
        $dropbox.on("drop", function(e) {
            e.preventDefault();
            $(this).removeClass("active");

            // Get the files.
            var files = e.originalEvent.dataTransfer.files;
            self.handleFiles(files);

            // Update the display to acknowledge the number of pending files.
            $dropbox.text(self.PENDING_FILES.length + " files ready for upload!");
        });

        // If the files are dropped outside of the drop zone, the browser will
        // redirect to show the files in the window. To avoid that we can prevent
        // the 'drop' event on the document.
        function stopDefault(e) {
            e.stopPropagation();
            e.preventDefault();
        }
        $(document).on("dragenter", stopDefault);
        $(document).on("dragover", stopDefault);
        $(document).on("drop", stopDefault);
    };
};

$(document).ready(function() {
    new RophakoUpload().ready();
});