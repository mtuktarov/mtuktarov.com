#!/usr/bin/env python

from django import template
from django.db.models import Q
from django.conf import settings
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
import random
from django.urls import reverse
from blog.models import Article, Category, Tag, Links, SideBar
from django.utils.encoding import force_text
from django.shortcuts import get_object_or_404
import hashlib
import urllib
from comments.models import Comment
from DjangoBlog.utils import cache_decorator, cache
from django.contrib.auth import get_user_model
from oauth.models import OAuthUser
from DjangoBlog.utils import get_current_site
import logging

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def timeformat(data):
    try:
        return data.strftime(settings.TIME_FORMAT)
        # print(data.strftime(settings.TIME_FORMAT))
        # return "ddd"
    except Exception as e:
        logger.error(e)
        return ""


@register.simple_tag
def datetimeformat(data):
    try:
        return data.strftime(settings.DATE_TIME_FORMAT)
    except Exception as e:
        logger.error(e)
        return ""


@register.filter(is_safe=True)
@stringfilter
def custom_markdown(content):
    # import requests
    # pload = {'markDownData': content}
    # r = requests.post('http://localhost:3000/markdown', data=pload)
    # return mark_safe(r.text)

    from DjangoBlog.utils import CommonMarkdown
    return mark_safe(CommonMarkdown.get_markdown(content))


@register.filter(is_safe=True)
@stringfilter
def truncatechars_content(content):
    """
    Get a summary of article content
    :param content:
    :return:
    """
    from django.template.defaultfilters import truncatechars_html
    from DjangoBlog.utils import get_blog_setting
    blogsetting = get_blog_setting()
    return truncatechars_html(content, blogsetting.article_sub_length)


@register.filter(is_safe=True)
@stringfilter
def truncate(content):
    from django.utils.html import strip_tags

    return strip_tags(content)[:150]


@register.inclusion_tag('blog/tags/breadcrumb.html')
def load_breadcrumb(article):
    """
    Get article breadcrumbs
    :param article:
    :return:
    """
    names = []
    if article.category is not None and len(article.category):
        names = article.get_category_tree()
    from DjangoBlog.utils import get_blog_setting
    blogsetting = get_blog_setting()
    site = get_current_site().domain
    names.append((blogsetting.sitename, '/'))
    names = names[::-1]

    return {
        'names': names,
        'title': article.title
    }


@register.inclusion_tag('blog/tags/article_tag_list.html')
def load_articletags(article):
    """
    Article tags
    :param article:
    :return:
    """
    tags = article.tags.all()
    tags_list = []
    for tag in tags:
        url = tag.get_absolute_url()
        count = tag.get_article_count()
        tags_list.append((
            url, count, tag, random.choice(settings.BOOTSTRAP_COLOR_TYPES)
        ))
    return {
        'article_tags_list': tags_list
    }


@register.inclusion_tag('blog/tags/sidebar.html')
def load_sidebar(user, linktype, request):
    """
    Load the sidebar
    :return:
    """
    # logger.info('load sidebar')
    # logger.info('request: {}'.format(request))
    from DjangoBlog.utils import get_blog_setting
    blogsetting = get_blog_setting()
    recent_articles = Article.objects.filter(status='p')[:blogsetting.sidebar_article_count]
    sidebar_categorys = Category.objects.all()
    extra_sidebars = SideBar.objects.filter(is_enabled=True).order_by('sequence')
    most_read_articles = Article.objects.filter(status='p').order_by('-views')[:blogsetting.sidebar_article_count]
    dates = Article.objects.datetimes('created_time', 'month', order='DESC')
    links = Links.objects.filter(is_enabled=True).filter(Q(show_type=str(linktype)) | Q(show_type='a'))
    commment_list = Comment.objects.filter(is_enabled=True).order_by('-id')[:blogsetting.sidebar_comment_count]
    unique_commment_list = []
    for comment in commment_list:
        if any(c.article.title == comment.article.title for c in unique_commment_list) and any(c.author.username == comment.author.username for c in unique_commment_list):
            continue
        unique_commment_list.append(comment)
    # Tag cloud calculate font size
    # Calculate the average value based on the total size (number / average) * step size
    increment = 5
    tags = Tag.objects.all()
    sidebar_tags = None
    if tags and len(tags) > 0:
        s = [t for t in [(t, t.get_article_count()) for t in tags] if t[1]]
        count = sum([t[1] for t in s])
        dd = 1 if (count == 0 or not len(tags)) else count / len(tags)
        import random
        sidebar_tags = list(map(lambda x: (x[0], x[1], (x[1] / dd) * increment + 10), s))
        random.shuffle(sidebar_tags)

    return {
        'recent_articles': recent_articles,
        'sidebar_categorys': sidebar_categorys,
        'most_read_articles': most_read_articles,
        'article_dates': dates,
        'sidebar_comments': unique_commment_list,
        'user': user,
        'sidabar_links': links,
        'show_google_adsense': blogsetting.show_google_adsense,
        'google_adsense_codes': blogsetting.google_adsense_codes,
        'enable_site_comment': blogsetting.enable_site_comment,
        'sidebar_tags': sidebar_tags,
        'show_views_bar': blogsetting.show_views_bar,
        'show_category_bar': blogsetting.show_category_bar,
        'show_search_bar': blogsetting.show_search_bar,
        'show_menu_bar': blogsetting.show_menu_bar,
        'extra_sidebars': extra_sidebars,
        'request': request
    }


@register.inclusion_tag('blog/tags/article_meta_info.html')
def load_article_metas(article, user):
    """
    Get article meta information
    :param article:
    :return:
    """
    return {
        'article': article,
        'user': user
    }


@register.inclusion_tag('blog/tags/article_pagination.html')
def load_pagination_info(page_obj, page_type, tag_name):
    previous_url = ''
    next_url = ''
    if page_type == '':
        if page_obj.has_next():
            next_number = page_obj.next_page_number()
            next_url = reverse('blog:index_page', kwargs={'page': next_number})
        if page_obj.has_previous():
            previous_number = page_obj.previous_page_number()
            previous_url = reverse('blog:index_page', kwargs={'page': previous_number})
    if page_type == 'Тег':
        tag = get_object_or_404(Tag, name=tag_name)
        if page_obj.has_next():
            next_number = page_obj.next_page_number()
            next_url = reverse('blog:tag_detail_page', kwargs={'page': next_number, 'tag_name': tag.slug})
        if page_obj.has_previous():
            previous_number = page_obj.previous_page_number()
            previous_url = reverse('blog:tag_detail_page', kwargs={'page': previous_number, 'tag_name': tag.slug})
    if page_type == 'Автор':
        if page_obj.has_next():
            next_number = page_obj.next_page_number()
            # next_url = reverse('blog:author_detail_page', kwargs={'page': next_number, 'author_name': tag_name})
        if page_obj.has_previous():
            previous_number = page_obj.previous_page_number()
            # previous_url = reverse('blog:author_detail_page', kwargs={'page': previous_number, 'author_name': tag_name})

    if page_type == 'Категория':
        category = get_object_or_404(Category, name=tag_name)
        if page_obj.has_next():
            next_number = page_obj.next_page_number()
            next_url = reverse('blog:category_detail_page',
                               kwargs={'page': next_number, 'category_name': category.slug})
        if page_obj.has_previous():
            previous_number = page_obj.previous_page_number()
            previous_url = reverse('blog:category_detail_page',
                                   kwargs={'page': previous_number, 'category_name': category.slug})

    return {
        'previous_url': previous_url,
        'next_url': next_url,
        'page_obj': page_obj
    }


"""
@register.inclusion_tag('nav.html')
def load_nav_info():
    category_list = Category.objects.all()
    return {
        'nav_category_list': category_list
    }
"""


@register.inclusion_tag('blog/tags/article_info.html')
def load_article_detail(article, isindex, user):
    """
    Loading article details
    :param article:
    :param isindex: List page containing only summary
    :return:
    """
    from DjangoBlog.utils import get_blog_setting
    blogsetting = get_blog_setting()

    return {
        'article': article,
        'isindex': isindex,
        'user': user,
        'enable_site_comment': blogsetting.enable_site_comment,
        'show_views_bar': blogsetting.show_views_bar,
    }


# return only the URL of the gravatar
# TEMPLATE USE:  {{ email|gravatar_url:150 }}
@register.filter
def gravatar_url(email, size=40):
    """Get gravatar avatar"""
    cachekey = 'gravatat/' + email
    if cache.get(cachekey):
        return cache.get(cachekey)
    else:
        usermodels = OAuthUser.objects.filter(email=email)
        if usermodels:
            o = list(filter(lambda x: x.picture is not None, usermodels))
            if o:
                return o[0].picture
        email = email.encode('utf-8')

        default = "https://mtuktarov.ru/static/blog/img/avatar.png".encode('utf-8')

        url = "https://www.gravatar.com/avatar/%s?%s" % (
            hashlib.md5(email.lower()).hexdigest(), urllib.parse.urlencode({'d': default, 's': str(size)}))
        cache.set(cachekey, url, 60 * 60 * 10)
        return url


@register.filter
def gravatar(email, size=40):
    """Get gravatar avatar"""
    url = gravatar_url(email, size)
    return mark_safe('<img src="%s" height="%d" width="%d">' % (url, size, size))


@register.simple_tag
def query(qs, **kwargs):
    """ template tag which allows queryset filtering. Usage:
          {% query books author=author as mybooks %}
          {% for book in mybooks %}
            ...
          {% endfor %}
    """
    return qs.filter(**kwargs)


def key(d, key_name):
    return d[key_name]


key = register.filter('key', key)


@register.filter
def rain(d):
    if settings.WEATHER in 'rain':
        return True
    return False


@register.filter
def snow(d):
    if settings.WEATHER in 'snow':
        return True
    return False
