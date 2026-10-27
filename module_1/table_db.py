TABLES = [
    """CREATE TABLE IF NOT EXISTS ITEMS_CODE (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name_line_code VARCHAR(255) NOT NULL UNIQUE,
        assign_register VARCHAR(255),
        value_bit_on INT NOT NULL,
        value_bit_off INT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS NUMS_CAMERA (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nums_camera INT,
        device_type VARCHAR(255),
        device_serial VARCHAR(255),
        connection_type VARCHAR(255),
        ip_address VARCHAR(255),
        item_code_id INT NOT NULL,
        FOREIGN KEY (item_code_id) REFERENCES ITEMS_CODE(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS NUMS_MODEL (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nums_model INT NOT NULL,
        camera_id INT NOT NULL,
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS WEIGHTS (
        id INT AUTO_INCREMENT PRIMARY KEY,
        Weight_Path TEXT NOT NULL,
        Activity_History_Path TEXT,
        Conf_Value INT DEFAULT 0,
        Size_Value INT DEFAULT 0,
        Device VARCHAR(255),
        Source VARCHAR(255),
        Task VARCHAR(255),
        Model_Runtime VARCHAR(255),
        Weight_TensorRT_Path TEXT,
        Classes_File_Path TEXT,
        IOU_Value INT DEFAULT 45,
        Max_Detections INT DEFAULT 100,
        Image_format VARCHAR(255),
        Folder_NG_Original_Path TEXT,
        Save_NG_Original BOOLEAN DEFAULT FALSE,
        Folder_NG_Detected_Path TEXT,
        Save_NG_Detected BOOLEAN DEFAULT FALSE,
        Folder_OK_Original_Path TEXT,
        Save_OK_Original BOOLEAN DEFAULT FALSE,
        Folder_OK_Detected_Path TEXT,
        Save_OK_Detected BOOLEAN DEFAULT FALSE,
        Folder_Image_Logging TEXT,
        model_id INT NOT NULL,
        FOREIGN KEY (model_id) REFERENCES NUMS_MODEL(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS PARAMETERSET (
        id INT AUTO_INCREMENT PRIMARY KEY,
        Label_Name TEXT NOT NULL,
        `Join` BOOLEAN DEFAULT FALSE,
        OK BOOLEAN DEFAULT FALSE,
        NG BOOLEAN DEFAULT FALSE,
        Quantity INT DEFAULT 0,
        Width_Min INT DEFAULT 0,
        Width_Max INT DEFAULT 0,
        Height_Min INT DEFAULT 0,
        Height_Max INT DEFAULT 0,
        Assign_Value VARCHAR(255) DEFAULT 0,
        Value INT DEFAULT 0,
        Confidence INT DEFAULT 0,
        model_id INT NOT NULL,
        FOREIGN KEY (model_id) REFERENCES NUMS_MODEL(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS MODE_AUTO (
        id INT AUTO_INCREMENT PRIMARY KEY,
        mode_name VARCHAR(255) NOT NULL,
        assign_register VARCHAR(255),
        value_bit_on INT NOT NULL,
        value_bit_off INT NOT NULL,
        camera_id INT NOT NULL,
        UNIQUE (mode_name, camera_id),
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS DEFAULT_MODE_AUTO (
        id INT AUTO_INCREMENT PRIMARY KEY,
        mode_name VARCHAR(255) NOT NULL,
        camera_id INT NOT NULL,
        UNIQUE (mode_name, camera_id),
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS MODE_AUTO_SIGNAL (
        id INT AUTO_INCREMENT PRIMARY KEY,
        signal_name VARCHAR(255) NOT NULL,
        address VARCHAR(255),
        read_register VARCHAR(255),
        read_value_on VARCHAR(255),
        read_value_off VARCHAR(255),
        write_register VARCHAR(255),
        write_value_on VARCHAR(255),
        write_value_off VARCHAR(255),
        mode_id INT NOT NULL,
        FOREIGN KEY (mode_id) REFERENCES MODE_AUTO(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS SHOTXMODEL (
        id INT AUTO_INCREMENT PRIMARY KEY,
        shot INT NOT NULL,
        no_of_model INT NOT NULL,
        mode_id INT NOT NULL,
        FOREIGN KEY (mode_id) REFERENCES MODE_AUTO(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS USER_SET_CAMERA (
        id INT AUTO_INCREMENT PRIMARY KEY,
        index_user_selector INT NOT NULL,
        user_set_selector VARCHAR(255) NOT NULL,
        mode_id INT NOT NULL,
        FOREIGN KEY (mode_id) REFERENCES MODE_AUTO(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS PLC_DATA (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ip_v4 VARCHAR(255),
        port VARCHAR(255),
        type_dev VARCHAR(255),
        protocol VARCHAR(255)
    )""",
    """CREATE TABLE IF NOT EXISTS MIRROR_CONFIG (
        id INT AUTO_INCREMENT PRIMARY KEY,
        parameter_name VARCHAR(255) NOT NULL,
        result_value VARCHAR(255),
        min_value VARCHAR(255),
        max_value VARCHAR(255),
        status VARCHAR(255),
        camera_id INT NOT NULL,
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS signal_transmission_and_reception (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        phase           ENUM('before','after') NOT NULL,
        signal_name     ENUM('gate','busy','ready') NOT NULL,
        is_join         TINYINT(1) NOT NULL DEFAULT 1,
        ordinal_number  INT NOT NULL,
        value_reg       VARCHAR(255) NOT NULL,
        camera_id       INT NOT NULL,
        UNIQUE KEY uq_camera_phase_signal (camera_id, phase, signal_name),
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS signal_timing_config (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        camera_id       INT NOT NULL,
        phase           ENUM('before','after') NOT NULL,
        signal_name     ENUM('gate','busy','ready') NOT NULL,
        delay_before    TINYINT(1) NOT NULL DEFAULT 0,
        delay_after     TINYINT(1) NOT NULL DEFAULT 0,
        timer_ms        FLOAT NOT NULL DEFAULT 0,
        UNIQUE KEY uq_camera_phase_signal (camera_id, phase, signal_name),
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS auto_logging (
        id INT AUTO_INCREMENT PRIMARY KEY,
        folder_path VARCHAR(255) NOT NULL,
        join_state TINYINT(1) NOT NULL DEFAULT 1,
        image_path VARCHAR(255) NOT NULL,
        description_image VARCHAR(255) NOT NULL,
        select_camera VARCHAR(255) NOT NULL,
        select_model VARCHAR(255) NOT NULL,
        register VARCHAR(255) NOT NULL,
        value_on VARCHAR(255) NOT NULL,
        value_off VARCHAR(255) NOT NULL,
        camera_id INT NOT NULL,
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE  
        )
    """,
    """
    CREATE TABLE IF NOT EXISTS counter_shot_setup (
        id                  INT AUTO_INCREMENT PRIMARY KEY,
        camera_id           INT NOT NULL,
        setup_counter_shot  VARCHAR(255) NOT NULL DEFAULT 'PC',
        reset_counter       VARCHAR(255) NOT NULL DEFAULT 'NONE',
        method_use          VARCHAR(255) NOT NULL DEFAULT 'Cycle',
        increment_counter_signal_selected VARCHAR(255) NOT NULL DEFAULT 'NONE',
        reset_counter_signal_selected   VARCHAR(255) NOT NULL DEFAULT 'NONE',
        method_use_signal_selected      VARCHAR(255) NOT NULL DEFAULT 'NONE',
        UNIQUE KEY uq_camera_counter_setup (camera_id),
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS setup_mapping_mode (
        id                  INT AUTO_INCREMENT PRIMARY KEY,
        camera_id           INT NOT NULL,
        mode_name           VARCHAR(50) NOT NULL,
        mapping_mode        VARCHAR(255),
        trigger_selected    VARCHAR(255),
        component           VARCHAR(255),
        completed           VARCHAR(255),
        UNIQUE KEY uq_camera_mapping_mode (camera_id, mode_name),
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS mode_display (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        display_mode    VARCHAR(255) NOT NULL,
        layout_mode     VARCHAR(255) NOT NULL,
        show_layout     VARCHAR(255) NOT NULL,
        item_code_id INT NOT NULL,
        FOREIGN KEY (item_code_id) REFERENCES ITEMS_CODE(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS task_calculator (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        camera_id       INT NOT NULL,
        task_name       VARCHAR(255) NOT NULL,
        task_type       VARCHAR(50) NOT NULL DEFAULT 'RELATION_COORDINATE',
        logic_mode      VARCHAR(20) NOT NULL DEFAULT 'ALL_PASS',
        action_on_fail  VARCHAR(20) NOT NULL DEFAULT 'NG',
        enabled         TINYINT(1) NOT NULL DEFAULT 1,
        assign_register VARCHAR(255) DEFAULT '',
        value_bit_on    INT DEFAULT 1,
        value_bit_off   INT DEFAULT 0,
        datetime        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS task_calculator_rules (
        id                      INT AUTO_INCREMENT PRIMARY KEY,
        task_id                 INT NOT NULL,
        rule_name               VARCHAR(255),
        label_1                 VARCHAR(255) NOT NULL,
        param_1                 VARCHAR(50) NOT NULL,
        instance_select_1       VARCHAR(50) NOT NULL DEFAULT 'BEST_CONF',
        operator                VARCHAR(20) NOT NULL,
        target_type             VARCHAR(50) NOT NULL DEFAULT 'LABEL',
        label_2                 VARCHAR(255),
        param_2                 VARCHAR(50),
        instance_select_2       VARCHAR(50) NOT NULL DEFAULT 'BEST_CONF',
        math_op                 VARCHAR(10) DEFAULT 'NONE',
        math_operand_type       VARCHAR(50) DEFAULT 'CONSTANT',
        math_operand_val        VARCHAR(255) DEFAULT '0',
        min_value               DOUBLE DEFAULT 0,
        max_value               DOUBLE DEFAULT 0,
        condition_true_result   VARCHAR(10) NOT NULL DEFAULT 'NG',
        enabled                 TINYINT(1) NOT NULL DEFAULT 1,
        description             TEXT,
        FOREIGN KEY (task_id) REFERENCES task_calculator(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
]


TABLES_SQL_DATA_AUTO_LOGIN = [
    """
    CREATE DATABASE IF NOT EXISTS DATA_AUTO_LOGIN;
    """,
    """CREATE TABLE IF NOT EXISTS DATA_AUTO_LOGIN.INFOR (
        id INT AUTO_INCREMENT PRIMARY KEY,
        hostname VARCHAR(255),
        username VARCHAR(255),
        password VARCHAR(255),
        port VARCHAR(255),
        manual BOOLEAN DEFAULT FALSE,
        automatic BOOLEAN DEFAULT FALSE,
        credential BOOLEAN DEFAULT FALSE,
        retry_attemps INT NOT NULL
    )""",

]

TABLES_SQL_DATA_IP_ADDRESS = [
    """
    CREATE DATABASE IF NOT EXISTS DATA_IP_ADDRESS;
    """,
    """CREATE TABLE IF NOT EXISTS DATA_IP_ADDRESS.INFOR_ADDRESS (
        id INT AUTO_INCREMENT PRIMARY KEY,
        plc_module VARCHAR(255),
        connection_port VARCHAR(255),
        ip_address_plc VARCHAR(255),
        port_plc INT,
        manual BOOLEAN DEFAULT FALSE,
        automatic BOOLEAN DEFAULT FALSE,
        local_ip VARCHAR(255),
        retry_attempts INT NOT NULL DEFAULT 0,
        auto_reconnect_on_disconnect BOOLEAN DEFAULT FALSE,
        direct_to_plc BOOLEAN DEFAULT FALSE,
        indirect_from_log BOOLEAN DEFAULT FALSE
    )""",
]


TABLES_SQL_ITEM_CODE_SAVE = [
    """
    CREATE DATABASE IF NOT EXISTS ITEM_CODE_SAVE;
    """,
    """
    CREATE TABLE IF NOT EXISTS ITEM_CODE_SAVE.DATA_SAVE_DEFAULT (
        id               INT AUTO_INCREMENT PRIMARY KEY,
        name_item_code   VARCHAR(255),
        name_line        VARCHAR(255),
        mode_name        VARCHAR(255),
        date_time        DATETIME NOT NULL
    )
""",
]

_ADMIN_TABLES_SQL = [
    """
    CREATE DATABASE IF NOT EXISTS ADMINISTRATOR;
    """,
    """
    CREATE TABLE IF NOT EXISTS ADMINISTRATOR.ADMIN_USERS (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        username        VARCHAR(255) NOT NULL UNIQUE,
        password_hash   VARCHAR(255) NOT NULL,
        role            ENUM('read_only','modify','full_control') NOT NULL DEFAULT 'read_only',
        is_active       TINYINT(1) NOT NULL DEFAULT 1,
        created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_login      DATETIME DEFAULT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS ADMINISTRATOR.HARDWARE_KEY_CONFIG (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        serial_number   VARCHAR(255) NOT NULL UNIQUE,
        hash_code       VARCHAR(255) NOT NULL UNIQUE,
        description     VARCHAR(255) DEFAULT '',
        is_enabled      TINYINT(1) NOT NULL DEFAULT 1,
        registered_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS ADMINISTRATOR.SYSTEM_CONFIG (
        config_key      VARCHAR(100) PRIMARY KEY,
        config_value    TEXT,
        description     VARCHAR(255) DEFAULT '',
        updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
]