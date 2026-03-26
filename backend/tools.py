write_file_tool = {
    "name": "write_file",
    "description": "Writes content to a file at the specified path. Overwrites if exists.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the file to write to."
            },
            "content": {
                "type": "STRING",
                "description": "The content to write to the file."
            }
        },
        "required": ["path", "content"]
    }
}

create_directory_tool = {
    "name": "create_directory",
    "description": "Creates a folder on the Mac filesystem. Use an absolute path or a home-relative path like ~/Desktop/New Folder.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The full folder path to create."
            },
            "reveal_in_finder": {
                "type": "BOOLEAN",
                "description": "Whether to reveal the created folder in Finder afterwards."
            }
        },
        "required": ["path"]
    }
}

create_finder_file_tool = {
    "name": "create_finder_file",
    "description": "Creates a file on the Mac filesystem in a Finder-visible location.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The full file path to create, including file name."
            },
            "content": {
                "type": "STRING",
                "description": "Optional text content to place into the file."
            },
            "reveal_in_finder": {
                "type": "BOOLEAN",
                "description": "Whether to reveal the created file in Finder afterwards."
            }
        },
        "required": ["path"]
    }
}

open_mac_app_tool = {
    "name": "open_mac_app",
    "description": "Opens an installed macOS application by name, such as Safari, Finder, Spotify, Notes, or Terminal.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "The macOS application name to open."
            }
        },
        "required": ["app_name"]
    }
}

close_mac_app_tool = {
    "name": "close_mac_app",
    "description": "Closes an installed macOS application by name, such as Safari, Finder, Spotify, Notes, or Terminal.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "The macOS application name to close."
            }
        },
        "required": ["app_name"]
    }
}

open_camera_tool = {
    "name": "open_camera",
    "description": "Turns on the webcam feed in the Edith interface so live visual context is available.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

close_camera_tool = {
    "name": "close_camera",
    "description": "Turns off the webcam feed in the Edith interface and stops live camera capture.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

shutdown_edith_tool = {
    "name": "shutdown_edith",
    "description": "Powers off Edith and closes the desktop app completely.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

generate_formatted_document_tool = {
    "name": "generate_formatted_document",
    "description": "Creates a properly formatted document file package, such as a formal application, letter, resume, statement, or polished draft, and saves real files like DOCX and PDF. Supports standard mode and a slower precision DOCX mode.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "What document to create and what it should say."
            },
            "output_path": {
                "type": "STRING",
                "description": "Optional full output path or base filename. You can use a home-relative path like ~/Desktop/leave_application."
            },
            "formats": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Optional formats to create, such as docx, pdf, and html."
            },
            "mode": {
                "type": "STRING",
                "description": "Optional document mode: 'standard' for the current faster formatter, or 'precision_docx' for the slower higher-fidelity DOCX builder."
            }
        },
        "required": ["prompt"]
    }
}

generate_document_bundle_tool = {
    "name": "generate_document_bundle",
    "description": "Creates a folder containing multiple polished files around one topic, such as personality profiles, trait breakdowns, plans, or study packs.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "What multi-file folder to create and what should be inside it."
            },
            "output_path": {
                "type": "STRING",
                "description": "Optional destination folder path. If omitted, use the current project."
            }
        },
        "required": ["prompt"]
    }
}

generate_image_tool = {
    "name": "generate_image",
    "description": "Generates an image from a prompt, saves it locally, and opens it.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "The image prompt to generate."
            },
            "output_path": {
                "type": "STRING",
                "description": "Optional output file path. If omitted, save it inside the current project."
            }
        },
        "required": ["prompt"]
    }
}

send_email_tool = {
    "name": "send_email",
    "description": "Sends a real email through the configured backend provider, preferably ClickSend. If sending is disabled, it may prepare a local draft path instead.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "to": {
                "type": "STRING",
                "description": "The recipient email address."
            },
            "subject": {
                "type": "STRING",
                "description": "The email subject line."
            },
            "body": {
                "type": "STRING",
                "description": "The email body."
            },
            "cc": {
                "type": "STRING",
                "description": "Optional CC recipient email addresses, comma-separated."
            },
            "send_now": {
                "type": "BOOLEAN",
                "description": "Whether to send the email immediately. If false, create a draft in Mail."
            }
        },
        "required": ["to", "subject", "body"]
    }
}

send_text_message_tool = {
    "name": "send_text_message",
    "description": "Sends a real SMS through the configured backend provider, preferably ClickSend.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "to": {
                "type": "STRING",
                "description": "The recipient phone number in international format, such as +9198...."
            },
            "message": {
                "type": "STRING",
                "description": "The message body to send."
            },
            "channel": {
                "type": "STRING",
                "description": "Optional channel: sms or whatsapp. Default to sms unless WhatsApp is explicitly requested."
            }
        },
        "required": ["to", "message"]
    }
}

reply_to_latest_communication_tool = {
    "name": "reply_to_latest_communication",
    "description": "Replies to the most recent relevant inbound email, SMS, or WhatsApp message using the configured provider. Default to SMS when starting a new phone-message reply unless the thread is already WhatsApp.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "message": {
                "type": "STRING",
                "description": "The reply message to send."
            },
            "channel": {
                "type": "STRING",
                "description": "Optional channel filter: email, sms, or whatsapp."
            },
            "query": {
                "type": "STRING",
                "description": "Optional sender/name query if Edith should reply to a specific recent communication."
            }
        },
        "required": ["message"]
    }
}

create_task_tool = {
    "name": "create_task",
    "description": "Creates a persistent task Edith can track across conversations, including optional due timing and priority.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "title": {
                "type": "STRING",
                "description": "The task title."
            },
            "details": {
                "type": "STRING",
                "description": "Optional extra details for the task."
            },
            "due_at": {
                "type": "STRING",
                "description": "Optional due time or date in natural language or a clear timestamp."
            },
            "priority": {
                "type": "STRING",
                "description": "Optional priority such as low, normal, high, or urgent."
            }
        },
        "required": ["title"]
    }
}

list_tasks_tool = {
    "name": "list_tasks",
    "description": "Lists Edith's persistent tasks so she can brief sir on what is still open or what has been completed.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "status": {
                "type": "STRING",
                "description": "Optional task filter such as open, active, pending, done, or completed."
            }
        }
    }
}

complete_task_tool = {
    "name": "complete_task",
    "description": "Marks a persistent task as completed by task name or ID.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The task name or ID to complete."
            }
        },
        "required": ["query"]
    }
}

schedule_reminder_tool = {
    "name": "schedule_reminder",
    "description": "Creates a persistent reminder Edith can use in future conversations.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "title": {
                "type": "STRING",
                "description": "What the reminder is about."
            },
            "when": {
                "type": "STRING",
                "description": "When the reminder should matter, in natural language or a clear timestamp."
            },
            "note": {
                "type": "STRING",
                "description": "Optional extra note or instruction for the reminder."
            },
            "recurrence": {
                "type": "STRING",
                "description": "Optional recurrence such as once, daily, weekly, or schoolday."
            }
        },
        "required": ["title", "when"]
    }
}

list_reminders_tool = {
    "name": "list_reminders",
    "description": "Lists Edith's persistent reminders.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "status": {
                "type": "STRING",
                "description": "Optional reminder filter such as active or done."
            }
        }
    }
}

create_calendar_event_tool = {
    "name": "create_calendar_event",
    "description": "Creates a persistent calendar-style event Edith can remember and use in planning.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "title": {
                "type": "STRING",
                "description": "The event title."
            },
            "start_at": {
                "type": "STRING",
                "description": "The event start time."
            },
            "end_at": {
                "type": "STRING",
                "description": "Optional event end time."
            },
            "location": {
                "type": "STRING",
                "description": "Optional event location."
            },
            "notes": {
                "type": "STRING",
                "description": "Optional notes."
            }
        },
        "required": ["title", "start_at"]
    }
}

list_calendar_events_tool = {
    "name": "list_calendar_events",
    "description": "Lists Edith's upcoming persistent calendar-style events.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

set_voice_mode_tool = {
    "name": "set_voice_mode",
    "description": "Switches Edith's voice mode, such as standard, study, soft, command, or combat.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "The voice mode to activate."
            }
        },
        "required": ["mode"]
    }
}

set_stark_mode_tool = {
    "name": "set_stark_mode",
    "description": "Turns Stark mode on or off for system-wide macOS cursor control. Supports standard hand mode and advanced eye-tracking mode.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "enabled": {
                "type": "BOOLEAN",
                "description": "Whether Stark mode should be enabled."
            },
            "mode": {
                "type": "STRING",
                "description": "Optional mode: hand for standard hand tracking, or advanced for eye-tracking cursor mode."
            },
            "show_preview": {
                "type": "BOOLEAN",
                "description": "Optional. Show the camera preview window while Stark mode runs."
            }
        },
        "required": ["enabled"]
    }
}

run_browser_workflow_tool = {
    "name": "run_browser_workflow",
    "description": "Runs a higher-level visible-browser workflow in Chrome through Kapture, such as WhatsApp messaging, Gmail drafting, or YouTube control.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "workflow": {
                "type": "STRING",
                "description": "The workflow name, such as whatsapp_message, gmail_draft, or youtube_control."
            },
            "target": {
                "type": "STRING",
                "description": "The main target for the workflow, such as a contact name, YouTube query, or email recipient."
            },
            "message": {
                "type": "STRING",
                "description": "Optional message text or body content."
            },
            "subject": {
                "type": "STRING",
                "description": "Optional subject line for mail workflows."
            },
            "action": {
                "type": "STRING",
                "description": "Optional action for workflows like YouTube control, for example open_home, search, play_pause, skip_forward, or skip_ad."
            }
        },
        "required": ["workflow"]
    }
}

read_clipboard_tool = {
    "name": "read_clipboard",
    "description": "Reads the current text contents of the macOS clipboard so Edith can see what was copied.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

copy_to_clipboard_tool = {
    "name": "copy_to_clipboard",
    "description": "Copies text onto the macOS clipboard, for example a short answer, link, or summary.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "The text to place on the clipboard."
            }
        },
        "required": ["text"]
    }
}

list_mac_printers_tool = {
    "name": "list_mac_printers",
    "description": "Lists the printers available on this Mac and shows the default printer when possible.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

print_file_tool = {
    "name": "print_file",
    "description": "Prints a file on this Mac using the system printer. Use an absolute or home-relative path like ~/Desktop/file.pdf.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The file path to print."
            },
            "printer_name": {
                "type": "STRING",
                "description": "Optional printer name. If omitted, the system default printer is used."
            },
            "copies": {
                "type": "NUMBER",
                "description": "Optional number of copies."
            }
        },
        "required": ["path"]
    }
}

copy_file_tool = {
    "name": "copy_file",
    "description": "Copies an existing file by exact path or natural-language file name into another folder or destination path.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "source": {
                "type": "STRING",
                "description": "The file to copy, either by full path or by natural-language name like 'the networking paper'."
            },
            "destination": {
                "type": "STRING",
                "description": "Optional destination folder or full destination path. If omitted, use the current project folder."
            }
        },
        "required": ["source"]
    }
}

open_file_tool = {
    "name": "open_file",
    "description": "Opens an existing local file by path or natural-language file name. HTML and PDF files may be opened in Chrome when appropriate.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The file to open, either by full path or by natural-language name like 'the networking paper'."
            }
        },
        "required": ["target"]
    }
}

edit_file_tool = {
    "name": "edit_file",
    "description": "Edits an existing local file by exact path or natural-language file name and replaces its contents with the provided updated content.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The file to edit, either by full path or by natural-language name."
            },
            "content": {
                "type": "STRING",
                "description": "The full updated file content to write."
            }
        },
        "required": ["target", "content"]
    }
}

move_file_tool = {
    "name": "move_file",
    "description": "Moves an existing file by exact path or natural-language file name into another folder or destination path.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "source": {
                "type": "STRING",
                "description": "The file to move, either by full path or by natural-language name."
            },
            "destination": {
                "type": "STRING",
                "description": "Destination folder or full destination path."
            }
        },
        "required": ["source", "destination"]
    }
}

delete_file_tool = {
    "name": "delete_file",
    "description": "Deletes an existing local file by exact path or natural-language file name.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The file to delete, either by full path or by natural-language name."
            }
        },
        "required": ["target"]
    }
}

open_conversation_log_tool = {
    "name": "open_conversation_log",
    "description": "Opens a numbered conversation log file, such as the current conversation or conversation 12.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "conversation_number": {
                "type": "NUMBER",
                "description": "Optional conversation number to open. If omitted, open the current conversation log."
            }
        }
    }
}

get_current_time_tool = {
    "name": "get_current_time",
    "description": "Gets the current local date and time. Use this when sir asks for the time, date, or timezone-sensitive current timing.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "timezone": {
                "type": "STRING",
                "description": "Optional IANA timezone like Asia/Kolkata or America/New_York. If omitted, use Asia/Kolkata."
            }
        }
    }
}

list_devices_tool = {
    "name": "list_devices",
    "description": "Lists the available microphones, speakers, and webcams Edith can switch to.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}

switch_device_tool = {
    "name": "switch_device",
    "description": "Switches Edith to a different microphone, speaker, or webcam by natural-language device name.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "kind": {
                "type": "STRING",
                "description": "The device type to switch: microphone, speaker, or webcam."
            },
            "query": {
                "type": "STRING",
                "description": "The device name or phrase, such as 'my headphones' or 'FaceTime HD Camera'."
            }
        },
        "required": ["kind", "query"]
    }
}

read_directory_tool = {
    "name": "read_directory",
    "description": "Lists the contents of a directory.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the directory to list."
            }
        },
        "required": ["path"]
    }
}

read_file_tool = {
    "name": "read_file",
    "description": "Reads the content of a file.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the file to read."
            }
        },
        "required": ["path"]
    }
}

tools_list = [{"function_declarations": [
    create_directory_tool,
    create_finder_file_tool,
    open_mac_app_tool,
    close_mac_app_tool,
    open_camera_tool,
    close_camera_tool,
    shutdown_edith_tool,
    generate_formatted_document_tool,
    generate_document_bundle_tool,
    generate_image_tool,
    send_email_tool,
    send_text_message_tool,
    reply_to_latest_communication_tool,
    create_task_tool,
    list_tasks_tool,
    complete_task_tool,
    schedule_reminder_tool,
    list_reminders_tool,
    create_calendar_event_tool,
    list_calendar_events_tool,
    set_voice_mode_tool,
    set_stark_mode_tool,
    run_browser_workflow_tool,
    read_clipboard_tool,
    copy_to_clipboard_tool,
    list_mac_printers_tool,
    print_file_tool,
    copy_file_tool,
    open_file_tool,
    edit_file_tool,
    move_file_tool,
    delete_file_tool,
    open_conversation_log_tool,
    get_current_time_tool,
    list_devices_tool,
    switch_device_tool,
    write_file_tool,
    read_directory_tool,
    read_file_tool
]}]
