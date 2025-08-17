#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

// Struct similar to Python's requests.Response object
typedef struct {
    char *body;
    size_t size;
    long status_code;
    char *url;
} Response;

// Struct for key-value pairs, similar to a Python dictionary
typedef struct {
    const char *key;
    const char *value;
} KeyValue;

// Callback function called by libcurl whenever data is received
static size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    Response *mem = (Response *)userp;
    char *ptr = realloc(mem->body, mem->size + realsize + 1);
    if (ptr == NULL) {
        printf("error: not enough memory (realloc returned NULL)\n");
        return 0;
    }
    mem->body = ptr;
    memcpy(&(mem->body[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->body[mem->size] = 0;
    return realsize;
}

// Function to free the memory of a Response object
void free_response(Response *response) {
    if (response) {
        free(response->body);
        free(response->url);
        free(response);
    }
}


/* requesrts_get function that performs an HTTP GET request
 * base_url: The base URL to which the request is made
 * params: Key-value pairs for query parameters, similar to a Python dictionary
 * headers: Key-value pairs for HTTP headers, similar to a Python dictionary
 * timeout_seconds: Timeout in seconds for the request, 0 means no timeout
 * Returns a Response object containing the response body, status code, and URL
 */
Response* requests_get(const char *base_url, const KeyValue *params, const KeyValue *headers, double timeout_seconds) {
    CURL *curl;
    CURLcode res;
    CURLU *h = NULL;
    CURLUcode uc;
    char *final_url_from_curl = NULL;

    // libcurl initialization
    Response *response = malloc(sizeof(Response));
    if (!response) {
        fprintf(stderr, "Failed to allocate memory for Response struct\n");
        return NULL;
    }
    response->body = malloc(1);
    response->size = 0;
    response->status_code = 0;
    response->url = NULL;
    
    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if (!curl) {
        fprintf(stderr, "Failed to initialize curl easy handle\n");
        free(response->body); free(response); curl_global_cleanup();
        return NULL;
    }

    h = curl_url();
    if (!h) {
        fprintf(stderr, "Failed to create curl URL handle\n");
        free(response->body); free(response); curl_easy_cleanup(curl); curl_global_cleanup();
        return NULL;
    }
    
    uc = curl_url_set(h, CURLUPART_URL, base_url, 0);
    if (uc) {
        fprintf(stderr, "Failed to set base URL: %s\n", curl_url_strerror(uc));
        free(response->body); free(response); curl_easy_cleanup(curl); curl_global_cleanup();
        curl_url_cleanup(h);
        return NULL;
    }

    // Add query parameters to the URL
    if (params) {
        for (int i = 0; params[i].key != NULL; i++) {
            // Dynamically create a "key=value" string.
            // If libcurl >= 7.80.0, CURLU_URLENCODE can be used, but for compatibility, we do it manually here.
            size_t kv_len = strlen(params[i].key) + strlen(params[i].value) + 2;
            char *kv_pair = malloc(kv_len);
            if (!kv_pair) {
                fprintf(stderr, "Failed to allocate memory for key-value pair\n");
                free(response->body); free(response); curl_easy_cleanup(curl); curl_global_cleanup();
                curl_url_cleanup(h);
                return NULL; 
            } // Memory allocation failed
            snprintf(kv_pair, kv_len, "%s=%s", params[i].key, params[i].value);

            // Add query parameter. CURLU_APPENDQUERY automatically adds '&' as needed.
            uc = curl_url_set(h, CURLUPART_QUERY, kv_pair, CURLU_APPENDQUERY | CURLU_URLENCODE);
            free(kv_pair);

            if (uc) {
                fprintf(stderr, "Failed to set query param: %s\n", curl_url_strerror(uc));
                free(response->body); free(response); curl_easy_cleanup(curl); curl_global_cleanup();
                curl_url_cleanup(h);
                return NULL;
            }
        }
    }
    
    uc = curl_url_get(h, CURLUPART_URL, &final_url_from_curl, 0);
    if (uc) {
        fprintf(stderr, "Failed to get full URL: %s\n", curl_url_strerror(uc));
        free(response->body); free(response); curl_easy_cleanup(curl); curl_global_cleanup();
        curl_url_cleanup(h);
        return NULL;
    }

    // Duplicate the final URL and store it in the response struct
    if (final_url_from_curl) {
        response->url = strdup(final_url_from_curl);
        if (!response->url) {
            fprintf(stderr, "Failed to duplicate final URL string.\n");
            
            curl_free(final_url_from_curl);
            curl_url_cleanup(h);
            curl_easy_cleanup(curl);
            free(response->body);
            free(response);
            curl_global_cleanup();
            return NULL;
        }
    }

    curl_easy_setopt(curl, CURLOPT_URL, response->url);


    struct curl_slist *header_list = NULL;
    if (headers) {
        for (int i = 0; headers[i].key != NULL; i++) {
            char header_string[256];
            snprintf(header_string, sizeof(header_string), "%s: %s", headers[i].key, headers[i].value);
            header_list = curl_slist_append(header_list, header_string);
        }
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, header_list);
    }
    
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)response);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "my-c-client/1.0");
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

    // Disable SSL verification for simplicity, but this is not recommended for production code
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);



    // set timeout if specified
    if (timeout_seconds > 0) {
        // Convert seconds to milliseconds for libcurl
        long timeout_ms = (long)(timeout_seconds * 1000.0);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, timeout_ms);
    }


    res = curl_easy_perform(curl);

    if (res != CURLE_OK) {
        fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
        free_response(response);
        response = NULL;
    } else {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response->status_code);
    }
    
    free(final_url_from_curl);
    curl_url_cleanup(h);
    curl_slist_free_all(header_list);

    curl_easy_cleanup(curl);
    curl_global_cleanup();

    return response;
}

