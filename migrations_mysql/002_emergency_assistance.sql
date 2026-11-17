CREATE TABLE IF NOT EXISTS data_sources (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_name VARCHAR(200) NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    published_on DATE NULL,
    checked_at DATE NULL,
    verification_status VARCHAR(24) NOT NULL DEFAULT 'NEEDS_REVIEW',
    notes VARCHAR(1000) NOT NULL DEFAULT '',
    UNIQUE INDEX uq_data_source_url (source_url(190))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS emergency_hotlines (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    service_name VARCHAR(200) NOT NULL,
    phone_number VARCHAR(40) NOT NULL,
    situations TEXT NOT NULL,
    keywords TEXT NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    source_published_on DATE NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX ix_hotline_active_verified (active, verified)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS emergency_faqs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX ix_faq_active_category (active, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS police_contacts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    unit_name VARCHAR(200) NOT NULL,
    station_name VARCHAR(200) NOT NULL,
    designation VARCHAR(120) NOT NULL,
    official_phone VARCHAR(120) NOT NULL DEFAULT '',
    listed_phone VARCHAR(120) NOT NULL DEFAULT '',
    new_phone VARCHAR(120) NOT NULL DEFAULT '',
    email VARCHAR(320) NOT NULL DEFAULT '',
    source_url VARCHAR(1000) NOT NULL,
    source_published_on DATE NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE INDEX uq_police_contact (unit_name(60), station_name(100), designation(40)),
    INDEX ix_police_contact_search (unit_name(60), station_name(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO data_sources
    (source_name, source_url, published_on, verification_status, notes)
VALUES
    (
        'Bangladesh Police contacts directory (XLSX)',
        'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf',
        '2020-10-03',
        'OUTDATED_REVIEW_REQUIRED',
        'The official directory page states that this spreadsheet was published on 03-10-2020. Imported contact numbers are unverified and must not be presented as current.'
    ),
    (
        'User-provided emergency hotline and guidance draft',
        'https://bangladesh.gov.bd/',
        NULL,
        'REVIEW_REQUIRED',
        'User-supplied numbers and advice require current official verification before being marked verified.'
    )
ON DUPLICATE KEY UPDATE
    source_name = VALUES(source_name),
    published_on = VALUES(published_on),
    verification_status = VALUES(verification_status),
    notes = VALUES(notes);

INSERT INTO emergency_hotlines
    (code, service_name, phone_number, situations, keywords, source_url, source_published_on, verified)
VALUES
    ('national-emergency', 'জাতীয় জরুরি সেবা', '999', 'তাৎক্ষণিক পুলিশ, অ্যাম্বুলেন্স বা ফায়ার সার্ভিস সহায়তা', '999|জরুরি|বিপদ|police|ambulance|emergency', 'https://bangladesh.gov.bd/', NULL, TRUE),
    ('fire-service', 'ফায়ার সার্ভিস', '102', 'আগুন বা উদ্ধার সহায়তা', 'আগুন|ফায়ার|ফায়ার সার্ভিস|fire|rescue|উদ্ধার', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('women-children', 'নারী ও শিশু সহায়তা', '109', 'নারী ও শিশু নির্যাতন-সংক্রান্ত সহায়তা', 'নারী|শিশু|নির্যাতন|violence|harassment', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('child-helpline', 'শিশু সহায়তা', '1098', 'শিশুর নিরাপত্তা, নির্যাতন বা নিখোঁজের বিষয়ে সহায়তা', 'শিশু|child|নিখোঁজ শিশু', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('government-services', 'সরকারি তথ্য ও সেবা', '333', 'সরকারি সেবা ও প্রশাসনিক তথ্য', 'সরকারি সেবা|তথ্য|333', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('disaster-warning', 'দুর্যোগের আগাম বার্তা', '1090', 'দুর্যোগ-সংক্রান্ত তথ্য ও আগাম বার্তা', 'দুর্যোগ|ঘূর্ণিঝড়|বন্যা|disaster|flood|cyclone', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('anti-corruption', 'দুর্নীতি দমন কমিশন', '106', 'দুর্নীতি ও অনিয়মের অভিযোগ', 'দুর্নীতি|অনিয়ম|corruption', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('legal-aid', 'সরকারি আইনগত সহায়তা', '16699', 'সরকারি আইনগত সহায়তা বিষয়ে তথ্য', 'আইনগত সহায়তা|legal aid|16699', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('court-information', 'সুপ্রিম কোর্ট হেল্পলাইন', '103', 'আদালত ও আইনি তথ্য', 'আদালত|court|103', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('coast-guard', 'কোস্ট গার্ড', '16111', 'উপকূল ও নৌপথের পরিস্থিতি', 'কোস্ট গার্ড|নৌ দুর্ঘটনা|coast guard|16111', 'https://bangladesh.gov.bd/', NULL, FALSE),
    ('drug-information', 'মাদক সংক্রান্ত তথ্য (খসড়ায় দেওয়া)', '01908-888888', 'মাদক সংক্রান্ত তথ্য', 'মাদক|drug|01908', 'https://bangladesh.gov.bd/', NULL, FALSE)
ON DUPLICATE KEY UPDATE
    service_name = VALUES(service_name),
    phone_number = VALUES(phone_number),
    situations = VALUES(situations),
    keywords = VALUES(keywords),
    source_url = VALUES(source_url),
    source_published_on = VALUES(source_published_on),
    verified = VALUES(verified),
    active = TRUE;

INSERT INTO emergency_faqs
    (category, question, answer, keywords, source_url, verified)
VALUES
    ('immediate-danger',
     'আমি বিপদে পড়েছি। এখন কী করব?',
     'নিরাপদ স্থানে যাওয়ার চেষ্টা করুন। তাৎক্ষণিক বিপদে জাতীয় জরুরি সেবা ৯৯৯-এ কল করুন। আপনার অবস্থান, কী ঘটেছে এবং কেউ আহত হয়েছেন কি না জানান। চ্যাটের উত্তরের জন্য অপেক্ষা করবেন না।',
     'বিপদে|জরুরি|emergency|danger|help me|999|হামলা|attack',
     'https://bangladesh.gov.bd/', TRUE),
    ('theft',
     'আমার মোবাইল ফোন চুরি হয়েছে। কী করব?',
     'আগে নিরাপদ স্থানে যান। সময় ও স্থান লিখে রাখুন, ফোনের IMEI বা কেনার প্রমাণ থাকলে সংরক্ষণ করুন, নিকটস্থ থানায় যোগাযোগ করে অভিযোগ বা জিডির উপযুক্ত পদ্ধতি জেনে নিন। মোবাইল ব্যাংকিং, SIM ও গুরুত্বপূর্ণ অ্যাকাউন্ট সুরক্ষিত করুন। চোরকে নিজে অনুসরণ বা মোকাবিলা করবেন না।',
     'মোবাইল|ফোন চুরি|চুরি|ছিনতাই|stolen phone|phone stolen|theft|robbery|IMEI',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('online-harassment',
     'কেউ আমাকে অনলাইনে ব্ল্যাকমেইল করছে।',
     'প্রোফাইল বা বার্তার লিংক, সময়সহ screenshot এবং প্রাসঙ্গিক প্রমাণ নিরাপদে রাখুন। টাকা পাঠানো বা একা দেখা করতে যাবেন না। বিশ্বস্ত ব্যক্তিকে জানান এবং নিকটস্থ থানা বা উপযুক্ত সাইবার অপরাধ কর্তৃপক্ষের কাছে অভিযোগের উপায় জেনে নিন। তাৎক্ষণিক শারীরিক হুমকিতে ৯৯৯-এ কল করুন।',
     'ব্ল্যাকমেইল|অনলাইন|সাইবার|হয়রানি|blackmail|online|cyber|threat|scam',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('missing-person',
     'আমার পরিবারের একজন সদস্য নিখোঁজ হয়েছেন।',
     'দেরি না করে নিকটস্থ থানায় জানান। সাম্প্রতিক ছবি, নাম, বয়স, পোশাক, সর্বশেষ দেখা স্থান ও সময়, এবং যোগাযোগের তথ্য দিন। তথ্যগুলো কেবল পুলিশ বা বিশ্বস্ত ব্যক্তির সঙ্গে ভাগ করুন, প্রকাশ্যে NID বা ব্যক্তিগত নম্বর পোস্ট করবেন না।',
     'নিখোঁজ|হারিয়ে গেছে|খুঁজে পাচ্ছি না|missing|disappeared|kidnapped|অপহরণ',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('threat',
     'কেউ আমাকে প্রাণনাশের হুমকি দিচ্ছে।',
     'নিরাপদ ও জনবহুল স্থানে যান এবং বিশ্বাসযোগ্য কাউকে জানান। তাৎক্ষণিক বিপদে ৯৯৯-এ কল করুন। হুমকির বার্তা, কলের সময় ও প্রাসঙ্গিক তথ্য সংরক্ষণ করুন, অভিযুক্তকে একা মোকাবিলা করবেন না।',
     'প্রাণনাশ|হুমকি|মেরে ফেল|threat|kill me|death threat|follow|পিছু নিচ্ছে',
     'https://bangladesh.gov.bd/', FALSE),
    ('complaint-refused',
     'পুলিশ অভিযোগ গ্রহণ না করলে কী করব?',
     'ঘটনার সময়-তারিখ ও কোথায় যোগাযোগ করেছেন তা লিখে রাখুন। দায়িত্বপ্রাপ্ত কর্মকর্তার ঊর্ধ্বতন বা সংশ্লিষ্ট জেলা/মহানগর পুলিশের দপ্তরে লিখিতভাবে জানান। কোন অভিযোগ বা আইনি পদ্ধতি প্রযোজ্য তা আইনজীবী বা সরকারি আইনগত সহায়তার সঙ্গে যাচাই করুন। আইনি সহায়তার নম্বরটি এই ডেটাবেসে যাচাই বাকি—জরুরি বিপদে ৯৯৯ ব্যবহার করুন।',
     'অভিযোগ নেয়নি|অভিযোগ গ্রহণ|পুলিশ অভিযোগ|আইনগত সহায়তা|complaint refused|police refused',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('reporting',
     'থানায় অভিযোগ জানাতে কী তথ্য লাগবে?',
     'ঘটনার সময়, তারিখ, স্থান, কী ঘটেছে এবং আপনার কাছে থাকা প্রাসঙ্গিক নথি বা প্রমাণ গুছিয়ে নিন। নিকটস্থ থানায় গিয়ে ডিউটি অফিসারকে জানান, জিডি, FIR বা অন্য কোন পদ্ধতি প্রযোজ্য তা পুলিশ বা আইনজীবীর সঙ্গে যাচাই করুন। জমা দেওয়া নথি ও রেফারেন্সের তথ্য রাখুন। তাৎক্ষণিক বিপদে ৯৯৯-এ কল করুন।',
     'থানায় অভিযোগ|অভিযোগ জানাতে|রিপোর্ট করতে|report|fir|complaint|জিডি করতে কী লাগে',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('online-gd',
     'থানায় না গিয়ে অনলাইনে জিডি করতে পারব?',
     'বাংলাদেশ পুলিশের Online GD পোর্টালে নির্ধারিত বিষয়ে আবেদন করা যায়। আবেদন জমা দেওয়ার পর portal-এর নির্দেশনা অনুসরণ করুন, অভিযোগের ধরন অনুযায়ী থানায় উপস্থিত হতে হতে পারে। অফিসিয়াল পোর্টাল: https://gd.police.gov.bd/',
     'জিডি|gd|অনলাইন জিডি|online gd|থানায় না গিয়ে|general diary',
     'https://gd.police.gov.bd/', FALSE),
    ('drug-report',
     'আমার এলাকায় মাদক বিক্রি হচ্ছে। কী করব?',
     'নিরাপদ দূরত্বে থাকুন এবং সন্দেহভাজন ব্যক্তিকে মোকাবিলা বা অনুসরণ করবেন না। সময়, জায়গা ও নিজের নিরাপত্তা বজায় রেখে জানা তথ্য নিকটস্থ থানায় জানান। জরুরি ঝুঁকিতে ৯৯৯-এ কল করুন। ডেটাবেসে থাকা বিশেষ মাদক-তথ্য নম্বরটি এখনো যাচাই হয়নি।',
     'মাদক|মাদক বিক্রি|drug|narcotics',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('street-harassment',
     'কেউ আমাকে অনুসরণ করছে বা রাস্তায় উত্ত্যক্ত করছে।',
     'জনবহুল, আলোযুক্ত ও নিরাপদ স্থানে যান—সম্ভব হলে পরিচিত দোকান বা নিরাপত্তাকর্মীর কাছে। বিশ্বস্ত কাউকে ফোন করুন। তাৎক্ষণিক হুমকিতে ৯৯৯-এ কল করে অবস্থান জানান। ওই ব্যক্তির মুখোমুখি হবেন না।',
     'উত্ত্যক্ত|ইভটিজিং|অনুসরণ|হয়রানি|harassment|followed|stalking|eve teasing',
     'https://bangladesh.gov.bd/', FALSE),
    ('road-accident',
     'সড়ক দুর্ঘটনা হলে কী করব?',
     'নিজের নিরাপত্তা নিশ্চিত করে ৯৯৯-এ কল করুন এবং সঠিক অবস্থান, আহতের সংখ্যা ও দৃশ্যমান ঝুঁকি জানান। আহত ব্যক্তিকে নড়াচড়া করানো বিপজ্জনক হতে পারে—প্রশিক্ষণ না থাকলে জরুরি সেবার নির্দেশনা অনুসরণ করুন।',
     'সড়ক দুর্ঘটনা|দুর্ঘটনা|বাস দুর্ঘটনা|road accident|crash|injured',
     'https://bangladesh.gov.bd/', TRUE),
    ('boat-accident',
     'নৌ দুর্ঘটনা হলে কী করব?',
     'নিজের নিরাপত্তা আগে নিশ্চিত করুন। সঠিক নদী/ঘাট/স্থান, নৌযানের পরিচয় এবং বিপদে থাকা মানুষের আনুমানিক সংখ্যা জানিয়ে ৯৯৯-এ কল করুন। উপকূল বা নৌপথের বিশেষ যোগাযোগ নম্বর হিসেবে এই ডেটাবেসে থাকা নম্বরটি যাচাই বাকি।',
     'নৌ দুর্ঘটনা|নৌযান|নৌকা|boat accident|launch accident|river accident|ডুবে',
     'https://bangladesh.gov.bd/', FALSE),
    ('fire',
     'আগুন লাগলে কাকে ফোন করব?',
     'ধোঁয়া বা আগুন থেকে নিরাপদে বেরিয়ে যান। লিফট ব্যবহার করবেন না এবং ফিরে গিয়ে জিনিস আনবেন না। জাতীয় জরুরি সেবা ৯৯৯-এ কল করে ঠিকানা ও আগুনের অবস্থা জানান। খসড়ায় উল্লেখিত ১০২ নম্বরের বর্তমান অবস্থা যাচাই বাকি—নিশ্চিত জরুরি যোগাযোগ হিসেবে ৯৯৯ ব্যবহার করুন।',
     'আগুন|অগ্নিকাণ্ড|fire|building fire|ধোঁয়া',
     'https://bangladesh.gov.bd/', TRUE),
    ('building-collapse',
     'ভবন ধস বা আটকে পড়ার ঘটনা হলে কী করব?',
     'ভবন থেকে নিরাপদ দূরত্বে সরে যান এবং ধসে পড়া অংশে প্রবেশ করবেন না। ৯৯৯-এ কল করে সঠিক ঠিকানা, আটকে পড়ার সম্ভাব্য সংখ্যা ও ঝুঁকি জানান। প্রশিক্ষিত উদ্ধারকারীদের নির্দেশনা অনুসরণ করুন।',
     'ভবন ধস|ধসে|আটকে পড়েছে|building collapse|trapped|rescue',
     'https://bangladesh.gov.bd/', TRUE),
    ('violence-safety',
     'নারী বা শিশু নির্যাতনের তাৎক্ষণিক ঝুঁকি থাকলে কী করব?',
     'সম্ভব হলে নিরাপদ স্থানে যান এবং বিশ্বস্ত ব্যক্তিকে জানান। তাৎক্ষণিক শারীরিক ঝুঁকিতে ৯৯৯-এ কল করুন। নারী ও শিশু-সংক্রান্ত বিশেষ হেল্পলাইন নম্বরগুলো এই ডেটাবেসে যাচাই বাকি, জরুরি মুহূর্তে যাচাই-অপেক্ষমাণ নম্বরের ওপর নির্ভর করবেন না।',
     'নারী নির্যাতন|শিশু নির্যাতন|পারিবারিক সহিংসতা|যৌন হয়রানি|বাল্যবিবাহ|women helpline|child abuse|domestic violence|sexual harassment',
     'https://bangladesh.gov.bd/', FALSE),
    ('lost-documents',
     'গুরুত্বপূর্ণ কাগজপত্র বা পরিচয়পত্র হারালে কী করব?',
     'কোন নথি, কোথায় ও আনুমানিক কখন হারিয়েছে তা লিখে রাখুন। নিকটস্থ থানায় যোগাযোগ করে জিডি বা অভিযোগের প্রয়োজন আছে কি না জেনে নিন, এরপর সংশ্লিষ্ট নথি-ইস্যুকারী কর্তৃপক্ষকে জানান। ব্যক্তিগত পরিচয় বা নথির ছবি প্রকাশ্যে শেয়ার করবেন না।',
     'কাগজপত্র হারিয়ে|NID হারিয়ে|পাসপোর্ট হারিয়ে|হারানো নথি|lost documents|lost ID|lost passport',
     'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf', FALSE),
    ('call-information',
     'পুলিশ বা জরুরি সেবায় ফোনে কী তথ্য দেব?',
     'প্রথমে আপনার অবস্থান ও কাছের পরিচিত স্থানের নাম বলুন। কী ঘটেছে, কখন ঘটেছে, কেউ আহত বা তাৎক্ষণিক ঝুঁকিতে আছে কি না জানান। নিজের নাম দিতে স্বাচ্ছন্দ্যবোধ করলে ও নিরাপদ হলে দিন। সন্দেহভাজনের কাছে যাবেন না এবং অনুমানকে নিশ্চিত তথ্য হিসেবে বলবেন না।',
     'ফোন করলে|কি তথ্য|কী তথ্য|কী বলব|999 এ কী|কল করলে|what information|what to say|call emergency',
     'https://bangladesh.gov.bd/', TRUE);
