var append_file = ((() => {
  pending_files = []
  var document_ready = false;

  document.addEventListener('DOMContentLoaded', (event) => {
    pending_files.forEach((item) => process_file(item.filename, item.id));
    document_ready = true;
  });

  function process_file(filename,id) {
    var iframe = document.createElement("iframe");
    iframe.src = filename + ".html?id=" + id;
    iframe.hidden = true;
    document.body.appendChild(iframe);
  }

  function append_file(filename, id)  {
    if (document_ready) {
      process_file(filename, id)
    } else {
      pending_files.push({filename: filename, id:id})
    }
  }

  return append_file;
})());


async function fetch(filename) {

  console.log("fetching: " + filename);

  function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  var id = uuidv4();

  var stream = new ReadableStream({
    start(controller) {
      function receiveMessage(event) {
        if (event.data.id === id) {
          if (event.data.data.length == 0) {
            controller.close();
          } else {
            controller.enqueue(event.data.data);
          }
        }
      }
      window.addEventListener("message", receiveMessage, false);
    }
  });
  var response = new Response(stream, {headers: new Headers([['Content-Type', 'application/wasm']])});
  append_file(filename, id);
  return response;
}

class XMLHttpRequest_ extends XMLHttpRequest {
  open(method, url) {
    console.log(method, url);
    this.open_promise = fetch(url).then((response) => response.blob().then((blob) => super.open(method, URL.createObjectURL(blob))));
  }
  send(data) {this.open_promise.then(() => super.send(data));}
}


XMLHttpRequest = XMLHttpRequest_;
