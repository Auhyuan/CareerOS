package com.careeros.common.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.module.SimpleModule;
import tools.jackson.databind.ser.std.ToStringSerializer;

@Configuration
public class LongSerialConfig {

    @Bean
    public SimpleModule longToStringModule() {

        SimpleModule simpleModule = new SimpleModule();
        simpleModule.addSerializer(Long.class, new ToStringSerializer(Long.class));
        simpleModule.addSerializer(Long.TYPE, new ToStringSerializer(Long.TYPE));

        return simpleModule;
    }
}
